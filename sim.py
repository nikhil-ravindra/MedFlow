"""
sim.py - the simulation engine: time passes minute by minute in the hospital.

Owner: Vansh.

Each simulated minute:
  1. Discharge  - patients whose treatment has finished give their resources back.
  2. Arrivals   - new patients join the waiting queue.
  3. Assignment - the chosen strategy orders the queue; we walk down that list
                  and give a patient ALL the resources they need, or nothing
                  (all-or-nothing). This makes double-booking and going over
                  capacity impossible.
  4. Snapshot   - record queue length and resources in use for the charts.
"""

import copy
import json
import math
import os
import random

from config import (
    AMBULANCE_RATE_PER_HOUR,
    ESI,
    FAILURE,
    FAILURE_DURATION_MIN,
    PATIENT_POOL_PATH,
    RESOURCE_TYPES,
    SHORTAGE,
    SURGE_DURATION_MIN,
    SURGE_MULTIPLIER,
)
from strategies import STRATEGIES


# ---------------------------------------------------------------------------
# Loading the AI-triaged patient pool
# ---------------------------------------------------------------------------
def load_patient_pool(path=PATIENT_POOL_PATH):
    """Read the patient templates that Nikhil's AI triage produced."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Run `python build_dataset.py` first "
            "(it needs GEMINI_API_KEY)."
        )
    with open(path, encoding="utf-8") as f:
        pool = json.load(f)
    pool = [p for p in pool if p.get("esi") in ESI]
    if not pool:
        raise ValueError(f"{path} has no valid patients.")
    return pool
