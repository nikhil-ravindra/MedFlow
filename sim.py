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
  # ---------------------------------------------------------------------------
# Random arrivals (Poisson process)
# ---------------------------------------------------------------------------
def _poisson(rng, lam):
    """Number of arrivals in one minute when on average `lam` arrive per minute.
    (Knuth's method - fine for small lam.)"""
    if lam <= 0:
        return 0
    limit = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _make_patient(rng, template, minute, source, pid):
    esi = template["esi"]
    low, high = ESI[esi]["treatment_minutes"]
    return {
        "id": pid,
        "arrival_time": minute,
        "source": source,
        "complaint": template["complaint"],
        "esi": esi,
        "needs": {r: int(template["needs"].get(r, 0)) for r in RESOURCE_TYPES},
        "treatment_time": rng.randint(low, high),
        "start_time": None,
        "end_time": None,
        "ai_reason": template.get("reason", ""),
    }


def generate_arrivals(pool, rate_per_hour, sim_minutes, seed=42,
                      surge=None, ambulance_rate_per_hour=0):
    """Create the list of patients who will arrive during the simulation.

    surge: None, or {"start": minute, "end": minute, "multiplier": 3}
    Walk-ins and ambulances use separate random generators, so switching
    ambulances on does not change who walks in.
    """
    walk_rng = random.Random(seed)
    amb_rng = random.Random(seed + 1000)
    ambulance_pool = [p for p in pool if p["esi"] <= 2]

