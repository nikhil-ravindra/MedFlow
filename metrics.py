"""
metrics.py - how well did the hospital do?

Owner: Om.
"""

import pandas as pd

from config import ESI, RESOURCE_TYPES
from sim import run_simulation
from strategies import STRATEGIES


def patient_table(results):
    """One row per patient with their wait and whether they were seen on time.

    Patients still waiting when the simulation ends get wait = end - arrival
    (the time they have waited so far) and count as NOT on time. Otherwise a
    strategy could look good just by never treating people.
    """
    sim_end = results["sim_minutes"]
    rows = []
    for p in results["patients"]:
        treated = p["start_time"] is not None
        wait = (p["start_time"] if treated else sim_end) - p["arrival_time"]
        rows.append({
            "id": p["id"],
            "source": p["source"],
            "esi": p["esi"],
            "complaint": p["complaint"],
            "ai_reason": p["ai_reason"],
            "arrival_time": p["arrival_time"],
            "start_time": p["start_time"],
            "end_time": p["end_time"],
            "wait": wait,
            "treated": treated,
            "on_time": treated and wait <= ESI[p["esi"]]["target_wait"],
        })
    return pd.DataFrame(rows)
