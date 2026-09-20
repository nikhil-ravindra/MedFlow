"""
build_dataset.py - send every complaint in data/complaints.txt through the AI
triage and save the results to data/patients.json.

Owner: Nikhil  Run:  python build_dataset.py

Complaints are sent in BATCHES (many patients per request) because the free
Gemini tier allows only a few requests per day. Results are cached, so running
the script again only sends the patients that are still missing.
"""

import json
import sys
import time
from collections import Counter

from config import PATIENT_POOL_PATH
from triage import MODEL, ConfigError, QuotaError, TriageError, triage_batch

COMPLAINTS_PATH = "data/complaints.txt"
BATCH_SIZE = 25        # patients per AI request (68 complaints -> 3 requests)
DELAY_SECONDS = 10     # pause between requests (per-minute limit)


def main():
    with open(COMPLAINTS_PATH, encoding="utf-8") as f:
        complaints = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    print(f"Triaging {len(complaints)} complaints with {MODEL} in batches of {BATCH_SIZE}...")
    results = [None] * len(complaints)
    for start in range(0, len(complaints), BATCH_SIZE):
        batch = complaints[start:start + BATCH_SIZE]
        try:
            batch_results = triage_batch(batch)
        except (ConfigError, QuotaError) as e:
            print(f"Stopped: {e}")
            break
        except TriageError as e:
            print(f"Batch starting at {start + 1} failed: {e}")
            continue
        results[start:start + len(batch)] = batch_results
        sent = any(r and not r["cached"] for r in batch_results)
        for i, r in enumerate(batch_results, start + 1):
            if r:
                tag = "cache" if r["cached"] else "AI"
                print(f"[{i}/{len(complaints)}] ESI {r['esi']} ({tag}) {r['complaint'][:60]}")
            else:
                print(f"[{i}/{len(complaints)}] missing - will retry next run")
        if sent and start + BATCH_SIZE < len(complaints):
            time.sleep(DELAY_SECONDS)

    pool = [{"complaint": r["complaint"], "esi": r["esi"], "needs": r["needs"],
             "reason": r["reason"], "model": r["model"]} for r in results if r]
    if not pool:
        print("Nothing triaged yet - patients.json not written.")
        sys.exit(1)

    with open(PATIENT_POOL_PATH, "w", encoding="utf-8") as f:
        json.dump(pool, f, indent=2)

    counts = Counter(p["esi"] for p in pool)
    print(f"\nSaved {len(pool)} of {len(complaints)} patients to {PATIENT_POOL_PATH}")
    print("ESI mix:", {k: counts[k] for k in sorted(counts)})
    if len(pool) < len(complaints):
        print("Some are missing - run the script again later to fill them in.")


if __name__ == "__main__":
    main()
