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
