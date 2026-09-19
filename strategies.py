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

