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


def compute_metrics(results):
    df = patient_table(results)
    timeline = results["timeline"]
    sim_minutes = results["sim_minutes"]

    # Resource utilisation = average (in use / capacity) over all minutes
    utilisation = {}
    for r in RESOURCE_TYPES:
        values = [s["used"][r] / s["capacity"][r] for s in timeline if s["capacity"][r] > 0]
        utilisation[r] = 100 * sum(values) / len(values) if values else 0.0

    queue_lengths = [s["queue_len"] for s in timeline]
    avg_queue = sum(queue_lengths) / len(queue_lengths) if queue_lengths else 0.0

    if df.empty:
        return {
            "summary": {"patients": 0, "treated": 0, "still_waiting": 0, "avg_wait": 0.0,
                        "pct_on_time": 0.0, "avg_queue": 0.0, "max_queue": 0},
            "by_esi": pd.DataFrame(),
            "utilisation": utilisation,
            "littles_law": {"lambda": 0.0, "W": 0.0, "L_predicted": 0.0, "L_measured": 0.0},
        }

    by_esi = (
        df.groupby("esi")
        .agg(patients=("id", "count"), treated=("treated", "sum"),
             avg_wait=("wait", "mean"), max_wait=("wait", "max"),
             pct_on_time=("on_time", "mean"))
        .reset_index()
    )
    by_esi["pct_on_time"] *= 100
    by_esi["target_wait"] = by_esi["esi"].map(lambda e: ESI[e]["target_wait"])

    summary = {
        "patients": len(df),
        "treated": int(df["treated"].sum()),
        "still_waiting": int((~df["treated"]).sum()),
        "avg_wait": float(df["wait"].mean()),
        "pct_on_time": float(100 * df["on_time"].mean()),
        "avg_queue": avg_queue,
        "max_queue": max(queue_lengths) if queue_lengths else 0,
    }

    # Little's law: average queue length L = arrival rate (lambda) x average wait W.
    # Our simulation should match it exactly - a good check that it is correct.
    lam = len(df) / sim_minutes
    W = float(df["wait"].mean())
    littles_law = {"lambda": lam, "W": W, "L_predicted": lam * W, "L_measured": avg_queue}

    return {"summary": summary, "by_esi": by_esi, "utilisation": utilisation,
            "littles_law": littles_law}
