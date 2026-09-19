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
