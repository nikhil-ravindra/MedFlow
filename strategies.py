"""
strategies.py - who gets treated first?

Owner: Om.

Every strategy is a function  f(queue, now) -> list  that returns the waiting
patients in the order they should be served. The simulation walks down that
list and treats everyone it has room for.
"""

from config import ESI


def fcfs(queue, now):
    """First come, first served: whoever arrived first goes first."""
    return sorted(queue, key=lambda p: (p["arrival_time"], p["id"]))


def urgency_only(queue, now):
    """Most urgent (lowest ESI) first; ties broken by arrival time."""
    return sorted(queue, key=lambda p: (p["esi"], p["arrival_time"], p["id"]))

# Patients at this ESI level or more urgent are ALWAYS served first.
CRITICAL_ESI = 2


def lateness(patient, now):
    """lateness = minutes waited / target wait for this ESI level.

    1.0 means "exactly at the target", 2.0 means "waited twice as long as
    allowed". Comparing lateness (not raw minutes) is fair across levels:
    30 min is a disaster for ESI 3 (target 30) but fine for ESI 5 (target 120).
    """
    waited = now - patient["arrival_time"]
    target = max(ESI[patient["esi"]]["target_wait"], 1)  # avoid divide by zero
    return waited / target


def urgency_plus_wait(queue, now):
    """Our strategy, in two tiers:
      1. Critical patients (ESI 1-2) always go first, most urgent first.
      2. Everyone else (ESI 3-5) is ordered by lateness - whoever is most
         overdue compared with their target goes next.
    Critical patients are protected exactly like 'urgency only', but a
    low-urgency patient can no longer be pushed back forever (no starvation).
    """
    def key(p):
        if p["esi"] <= CRITICAL_ESI:
            return (0, p["esi"], p["arrival_time"], p["id"])
        return (1, -lateness(p, now), p["arrival_time"], p["id"])
    return sorted(queue, key=key)
    
def urgency_shortest_first(queue, now):
    """Most urgent first; within the same urgency, shortest treatment first.
    (Shortest-job-first is the classic rule that minimises average waiting time.)"""
    return sorted(queue, key=lambda p: (p["esi"], p["treatment_time"], p["arrival_time"], p["id"]))


# The names shown in the dashboard dropdown -> the function to use.
STRATEGIES = {
    "First come, first served": fcfs,
    "Urgency only": urgency_only,
    "Urgency + waiting time (ours)": urgency_plus_wait,
    "Urgency + shortest job first": urgency_shortest_first,
}
