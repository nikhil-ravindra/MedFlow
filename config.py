"""
config.py - shared settings for MedFlow.

Owner: Person 1. Everyone imports from this file; only Person 1 edits it,
so the whole team always agrees on the same numbers.
"""

# The hospital resources we track. Every patient "needs" some of each.
RESOURCE_TYPES = ["bed", "icu_bed", "doctor", "nurse"]

# Default hospital size (the sidebar sliders start here).
# Simplification: a "doctor" or "nurse" here means one staff slot that stays
# with a patient for their whole treatment.
DEFAULT_RESOURCES = {"bed": 10, "icu_bed": 4, "doctor": 8, "nurse": 12}

# ESI = Emergency Severity Index, the standard 5-level emergency triage scale.
# 1 = most urgent, 5 = least urgent.
#   default_needs      resources a typical patient at this level uses
#   treatment_minutes  (min, max) treatment time, picked at random in between
#   target_wait        how long this patient should wait at most (minutes)
ESI = {
    1: {
        "name": "Resuscitation",
        "example": "cardiac arrest, not breathing, major trauma",
        "default_needs": {"bed": 0, "icu_bed": 1, "doctor": 1, "nurse": 2},
        "treatment_minutes": (120, 240),
        "target_wait": 0,
        "color": "#d62728",
    }
}
