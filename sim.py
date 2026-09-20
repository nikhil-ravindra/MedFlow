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

 patients = []
    for minute in range(sim_minutes):
        rate = rate_per_hour
        if surge and surge["start"] <= minute < surge["end"]:
            rate *= surge["multiplier"]

        for _ in range(_poisson(walk_rng, rate / 60)):
            template = walk_rng.choice(pool)
            patients.append(_make_patient(walk_rng, template, minute, "walk-in", len(patients)))

        if ambulance_pool and ambulance_rate_per_hour > 0:
            for _ in range(_poisson(amb_rng, ambulance_rate_per_hour / 60)):
                template = amb_rng.choice(ambulance_pool)
                patients.append(_make_patient(amb_rng, template, minute, "ambulance", len(patients)))
    return patients


# ---------------------------------------------------------------------------
# Scenario events (staff shortage, equipment failure)
# ---------------------------------------------------------------------------
def build_events(settings, sim_minutes, seed=42):
    """Turn the dashboard checkboxes into capacity-change events."""
    events = []
    if settings.get("staff_shortage"):
        start = sim_minutes // 2
        for resource, delta in SHORTAGE.items():
            events.append({"name": "Staff shortage", "resource": resource,
                           "delta": delta, "start": start, "end": sim_minutes})
    if settings.get("resource_failure"):
        rng = random.Random(seed + 7)
        start = rng.randint(sim_minutes // 4, sim_minutes // 2)
        for resource, delta in FAILURE.items():
            events.append({"name": "Equipment failure", "resource": resource,
                           "delta": delta, "start": start,
                           "end": min(start + FAILURE_DURATION_MIN, sim_minutes)})
    return events


def capacity_at(resources, events, minute):
    """How many of each resource exist at this minute, after events."""
    cap = dict(resources)
    for e in events:
        if e["start"] <= minute < e["end"]:
            cap[e["resource"]] = max(0, cap[e["resource"]] + e["delta"])
    return cap


def prepare_run(pool, settings, seed=42):
    """Everything needed before run_simulation: patients, events, length."""
    sim_minutes = int(settings["sim_hours"] * 60)
    surge = None
    if settings.get("surge"):
        start = sim_minutes // 4
        surge = {"start": start, "end": min(start + SURGE_DURATION_MIN, sim_minutes),
                 "multiplier": SURGE_MULTIPLIER}
    patients = generate_arrivals(
        pool, settings["rate_per_hour"], sim_minutes, seed=seed, surge=surge,
        ambulance_rate_per_hour=AMBULANCE_RATE_PER_HOUR if settings.get("ambulances") else 0,
    )
    events = build_events(settings, sim_minutes, seed)
    return patients, events, sim_minutes, surge
# ---------------------------------------------------------------------------
# The main simulation loop
# ---------------------------------------------------------------------------
def _fits(needs, used, cap):
    return all(used[r] + needs.get(r, 0) <= cap[r] for r in RESOURCE_TYPES)


def run_simulation(patients, resources, strategy_name, sim_minutes, events=None):
    """Run the hospital for `sim_minutes` using one scheduling strategy.

    The input `patients` list is not modified (we work on a copy), so the same
    patients can be replayed with every strategy for a fair comparison.
    """
    events = events or []
    order_queue = STRATEGIES[strategy_name]
    patients = copy.deepcopy(patients)

    arrivals_at = {}
    for p in patients:
        arrivals_at.setdefault(p["arrival_time"], []).append(p)

    queue, treating, timeline = [], [], []
    used = {r: 0 for r in RESOURCE_TYPES}

    for minute in range(sim_minutes):
        # 1. Discharge finished patients
        still_treating = []
        for p in treating:
            if p["end_time"] <= minute:
                for r in RESOURCE_TYPES:
                    used[r] -= p["needs"].get(r, 0)
            else:
                still_treating.append(p)
        treating = still_treating

        # 2. New arrivals join the queue
        queue.extend(arrivals_at.get(minute, []))

        # 3. Assign resources, all-or-nothing, in the strategy's order
        cap = capacity_at(resources, events, minute)
        for p in order_queue(queue, minute):
            if _fits(p["needs"], used, cap):
                for r in RESOURCE_TYPES:
                    used[r] += p["needs"].get(r, 0)
                p["start_time"] = minute
                p["end_time"] = minute + p["treatment_time"]
                treating.append(p)
        queue = [p for p in queue if p["start_time"] is None]

        # 4. Snapshot for the charts
        timeline.append({
            "t": minute,
            "queue_len": len(queue),
            "treating": len(treating),
            "used": dict(used),
            "capacity": cap,
        })

    return {
        "patients": patients,
        "timeline": timeline,
        "strategy": strategy_name,
        "sim_minutes": sim_minutes,
        "resources": dict(resources),
        "events": events,
    }

                    

