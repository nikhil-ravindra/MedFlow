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
