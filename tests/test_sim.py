"""
tests/test_sim.py - checks that the simulation obeys the rules.

Owner: Om.  Run with:  python -m pytest
The patients here are hand-written TEST data only - the real app uses the
AI-triaged data in data/patients.json.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import ESI, RESOURCE_TYPES  # noqa: E402
from metrics import compare_strategies, compute_metrics  # noqa: E402
from sim import build_events, capacity_at, generate_arrivals, run_simulation  # noqa: E402
from strategies import STRATEGIES  # noqa: E402

TEST_POOL = [
    {"complaint": f"test patient esi {e}", "esi": e, "needs": ESI[e]["default_needs"], "reason": "test"}
    for e in ESI
]
RESOURCES = {"bed": 10, "icu_bed": 4, "doctor": 8, "nurse": 12}


def _patients(rate=10, minutes=480, seed=1):
    return generate_arrivals(TEST_POOL, rate, minutes, seed=seed, ambulance_rate_per_hour=2)


def _usage_at(patients, minute):
    used = {r: 0 for r in RESOURCE_TYPES}
    for p in patients:
        if p["start_time"] is not None and p["start_time"] <= minute < p["end_time"]:
            for r in RESOURCE_TYPES:
                used[r] += p["needs"].get(r, 0)
    return used


def test_capacity_never_exceeded():
    patients = _patients()
    for name in STRATEGIES:
        res = run_simulation(patients, RESOURCES, name, 480)
        for minute in range(480):
            used = _usage_at(res["patients"], minute)
            for r in RESOURCE_TYPES:
                assert used[r] <= RESOURCES[r], (name, minute, r)


def test_events_reduce_capacity_for_new_patients():
    events = build_events({"staff_shortage": True, "resource_failure": True}, 480, seed=3)
    patients = _patients()
    res = run_simulation(patients, RESOURCES, "Urgency only", 480, events)
    for p in res["patients"]:
        if p["start_time"] is None:
            continue
        cap = capacity_at(RESOURCES, events, p["start_time"])
        used = _usage_at(res["patients"], p["start_time"])
        for r in RESOURCE_TYPES:
            assert used[r] <= max(cap[r], RESOURCES[r])


def test_littles_law_holds_exactly():
    patients = _patients()
    for name in STRATEGIES:
        m = compute_metrics(run_simulation(patients, RESOURCES, name, 480))
        ll = m["littles_law"]
        assert abs(ll["L_predicted"] - ll["L_measured"]) < 1e-9


def test_input_patients_not_modified():
    patients = _patients()
    run_simulation(patients, RESOURCES, "First come, first served", 480)
    assert all(p["start_time"] is None for p in patients)


def test_urgent_patient_goes_first():
    one_doctor = {"bed": 5, "icu_bed": 1, "doctor": 1, "nurse": 5}
    base = {"source": "walk-in", "complaint": "", "ai_reason": "", "start_time": None,
            "end_time": None, "treatment_time": 30}
    patients = [
        dict(base, id=0, arrival_time=0, esi=5, needs={"doctor": 1}),
        dict(base, id=1, arrival_time=0, esi=2, needs={"doctor": 1}),
    ]
    res = run_simulation(patients, one_doctor, "Urgency only", 120)
    starts = {p["id"]: p["start_time"] for p in res["patients"]}
    assert starts[1] == 0 and starts[0] == 30


def test_compare_strategies_has_one_row_each():
    table, _ = compare_strategies(_patients(), RESOURCES, 480)
    assert list(table["strategy"]) == list(STRATEGIES)
