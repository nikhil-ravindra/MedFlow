"""
triage.py - the AI component: an LLM reads a patient's complaint and decides
their urgency (ESI 1-5) and which resources they need.

Owner: Nikhil

Needs the environment variable GEMINI_API_KEY (free key from Google AI Studio).
Optional: GEMINI_MODEL to use a different model.

Rule: if the AI fails we raise an error and show "AI unavailable".
We NEVER quietly substitute hardcoded answers.
"""

import hashlib
import json
import os
import re
import time

from config import ESI, RESOURCE_TYPES

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
CACHE_PATH = "data/triage_cache.json"


class TriageError(Exception):
    """The AI could not produce a valid answer."""


class ConfigError(TriageError):
    """Setup problem (no API key, library missing) - retrying will not help."""


class QuotaError(TriageError):
    """Daily free-tier limit reached - retrying today will not help."""


def _is_daily_quota(error):
    text = str(error)
    return "RESOURCE_EXHAUSTED" in text and "PerDay" in text


# ---------------------------------------------------------------------------
# Talking to Gemini
# ---------------------------------------------------------------------------
def ask_gemini(prompt, json_mode=False, temperature=0.0):
    """Send a prompt to Gemini and return the text reply."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ConfigError("GEMINI_API_KEY is not set. Get a free key from Google AI Studio.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise ConfigError("Run: pip install google-genai") from e

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json" if json_mode else "text/plain",
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    response = client.models.generate_content(model=MODEL, contents=prompt, config=config)
    if not response.text:
        raise TriageError("Empty reply from the model.")
    return response.text


# ---------------------------------------------------------------------------
# The triage prompt
# ---------------------------------------------------------------------------
def _esi_table_text():
    lines = []
    for level, info in ESI.items():
        needs = ", ".join(f"{r}={n}" for r, n in info["default_needs"].items() if n)
        lines.append(f"ESI {level} ({info['name']}): e.g. {info['example']}. "
                     f"Typical needs: {needs}. Should be seen within {info['target_wait']} min.")
    return "\n".join(lines)


PROMPT_TEMPLATE = """You are an experienced emergency department triage nurse.
Classify the patient below using the Emergency Severity Index (ESI):

{table}

Also decide which hospital resources this patient needs right now:
- bed: a general emergency bed (0 or 1)
- icu_bed: an intensive care bed (0 or 1) - only for life-threatening cases
- doctor: number of doctors (1 or 2)
- nurse: number of nurses (0 to 2)
A patient uses a bed OR an icu_bed, never both.

Patient: \"\"\"{complaint}\"\"\"

Reply with ONLY this JSON, nothing else:
{{"esi": <1-5>, "needs": {{"bed": <n>, "icu_bed": <n>, "doctor": <n>, "nurse": <n>}}, "reason": "<one short sentence>"}}
"""


def _parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise TriageError(f"No JSON in reply: {text[:100]}")
    return json.loads(match.group(0))


def _validate(data):
    """Check the AI's answer and clean it up. Raise if it makes no sense."""
    esi = int(data["esi"])
    if esi not in ESI:
        raise TriageError(f"ESI must be 1-5, got {esi}")

    raw = data.get("needs") or {}
    needs = {r: max(0, min(2, int(raw.get(r, 0)))) for r in RESOURCE_TYPES}
    needs["bed"] = min(needs["bed"], 1)
    needs["icu_bed"] = min(needs["icu_bed"], 1)
    if needs["icu_bed"] and needs["bed"]:
        needs["bed"] = 0          # ICU patients do not also take a general bed
    if needs["doctor"] == 0:
        needs["doctor"] = 1       # everyone is seen by a doctor

    reason = str(data.get("reason", "")).strip()[:200]
    return {"esi": esi, "needs": needs, "reason": reason}


# ---------------------------------------------------------------------------
# Cache (so the same complaint is never sent twice - faster, saves quota)
# ---------------------------------------------------------------------------
def _key(complaint):
    return hashlib.sha1(" ".join(complaint.lower().split()).encode()).hexdigest()


def _load_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------
def triage(complaint, use_cache=True):
    """Return {"esi", "needs", "reason", "model", "cached"} for one complaint."""
    complaint = complaint.strip()
    if not complaint:
        raise TriageError("Complaint is empty.")

    cache = _load_cache()
    key = _key(complaint)
    if use_cache and key in cache:
        return {**cache[key], "cached": True}

    prompt = PROMPT_TEMPLATE.format(table=_esi_table_text(), complaint=complaint)
    last_error = None
    for attempt in range(4):                      # retry: busy server or broken reply
        try:
            result = _validate(_parse_json(ask_gemini(prompt, json_mode=True)))
            break
        except ConfigError:
            raise
        except Exception as e:                    # bad JSON, API hiccup, rate limit...
            if _is_daily_quota(e):
                raise QuotaError("Daily free quota for this model is used up. "
                                 "Use another model (GEMINI_MODEL) or a teammate's key.") from e
            last_error = e
            time.sleep(5 * (attempt + 1))         # wait 5, 10, 15 s before trying again
    else:
        raise TriageError(f"AI triage failed: {last_error}")

    result["model"] = MODEL
    result["complaint"] = complaint
    cache[key] = result
    _save_cache(cache)
    return {**result, "cached": False}


# ---------------------------------------------------------------------------
# Batch triage: many patients in ONE request (saves the free-tier quota)
# ---------------------------------------------------------------------------
BATCH_PROMPT_TEMPLATE = PROMPT_TEMPLATE.split("Patient:")[0] + """Patients:
{patients}

Reply with ONLY a JSON array - one object per patient, same order, nothing else:
[{{"id": <patient number>, "esi": <1-5>, "needs": {{"bed": <n>, "icu_bed": <n>, "doctor": <n>, "nurse": <n>}}, "reason": "<one short sentence>"}}, ...]
"""


def _parse_json_array(text):
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    match = re.search(r"\[.*\]", text, flags=re.DOTALL)
    if not match:
        raise TriageError(f"No JSON array in reply: {text[:100]}")
    return json.loads(match.group(0))


def triage_batch(complaints):
    """Triage a list of complaints with ONE AI request.

    Returns a list the same length as `complaints`; each item is a result
    dict (like triage()) or None if the AI skipped / garbled that patient.
    Already-cached complaints are not sent again.
    """
    cache = _load_cache()
    results = [None] * len(complaints)
    to_send = []
    for i, c in enumerate(complaints):
        key = _key(c)
        if key in cache:
            results[i] = {**cache[key], "cached": True}
        else:
            to_send.append(i)
    if not to_send:
        return results

    numbered = "\n".join(f"{n}. {complaints[i]}" for n, i in enumerate(to_send, 1))
    prompt = BATCH_PROMPT_TEMPLATE.format(table=_esi_table_text(), patients=numbered)

    last_error = None
    for attempt in range(3):
        try:
            items = _parse_json_array(ask_gemini(prompt, json_mode=True))
            break
        except ConfigError:
            raise
        except Exception as e:
            if _is_daily_quota(e):
                raise QuotaError("Daily free quota for this model is used up. "
                                 "Use another model (GEMINI_MODEL) or a teammate's key.") from e
            last_error = e
            time.sleep(15 * (attempt + 1))        # wait 15, 30 s (per-minute limit)
    else:
        raise TriageError(f"AI batch triage failed: {last_error}")

    for item in items:
        try:
            n = int(item["id"])
            i = to_send[n - 1]
            result = _validate(item)
        except Exception:
            continue                              # skip a garbled entry; it is retried next run
        result["model"] = MODEL
        result["complaint"] = complaints[i]
        cache[_key(complaints[i])] = result
        results[i] = {**result, "cached": False}
    _save_cache(cache)
    return results


if __name__ == "__main__":
    # Quick manual test:  python triage.py "chest pain, sweating, BP 90/60"
    import sys
    text = " ".join(sys.argv[1:]) or "crushing chest pain spreading to left arm, sweating, BP 90/60"
    print(json.dumps(triage(text, use_cache=False), indent=2))
