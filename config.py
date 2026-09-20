"""
config.py - shared settings for MedFlow.

Owner: Vansh. Everyone imports from this file; only Vansh edits it,
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
    2: {
        "name": "Emergent",
        "example": "chest pain, stroke symptoms, severe breathing trouble",
        "default_needs": {"bed": 1, "icu_bed": 0, "doctor": 1, "nurse": 1},
        "treatment_minutes": (60, 120),
        "target_wait": 10,
        "color": "#ff7f0e",
    },
    3: {
        "name": "Urgent",
        "example": "high fever, suspected fracture, abdominal pain",
        "default_needs": {"bed": 1, "icu_bed": 0, "doctor": 1, "nurse": 1},
        "treatment_minutes": (45, 90),
        "target_wait": 30,
        "color": "#e6b800",
    },
    4: {
        "name": "Less urgent",
        "example": "small cut needing stitches, sprained ankle",
        "default_needs": {"bed": 0, "icu_bed": 0, "doctor": 1, "nurse": 1},
        "treatment_minutes": (20, 40),
        "target_wait": 60,
        "color": "#7cb342",
    },
    5: {
        "name": "Non-urgent",
        "example": "prescription refill, mild cold",
        "default_needs": {"bed": 0, "icu_bed": 0, "doctor": 1, "nurse": 0},
        "treatment_minutes": (10, 20),
        "target_wait": 120,
        "color": "#2e7d32",
    },
}

# Default simulation settings.
SIM_DEFAULTS = {"rate_per_hour": 5, "sim_hours": 12}

# Scenario settings used when a checkbox is ticked in the dashboard.
SURGE_MULTIPLIER = 3          # arrivals x3 during a surge
SURGE_DURATION_MIN = 120      # surge lasts 2 hours
AMBULANCE_RATE_PER_HOUR = 2   # extra high-urgency arrivals
SHORTAGE = {"doctor": -2, "nurse": -3}             # staff lost for the 2nd half
FAILURE = {"bed": -3, "icu_bed": -1}               # equipment out of service
FAILURE_DURATION_MIN = 90

# Where the AI-triaged patient data lives (made by build_dataset.py).
PATIENT_POOL_PATH = "data/patients.json"

