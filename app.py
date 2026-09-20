"""
app.py - the MedFlow dashboard.

Owner: Person 3.   Run:  streamlit run app.py
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from config import DEFAULT_RESOURCES, ESI, RESOURCE_TYPES, SIM_DEFAULTS
from metrics import compare_strategies, compute_metrics, patient_table
from sim import load_patient_pool, prepare_run, run_simulation
from strategies import STRATEGIES
from triage import TriageError, triage

st.set_page_config(page_title="MedFlow", page_icon="🏥", layout="wide")

ESI_COLORS = {f"ESI {k}": v["color"] for k, v in ESI.items()}
ESI_DOTS = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "🟩"}
RESOURCE_LABELS = {"bed": "Beds", "icu_bed": "ICU beds", "doctor": "Doctors", "nurse": "Nurses"}

st.title("🏥 MedFlow")
st.caption("Prioritize patients. Optimize resources. — a hospital resource management simulator")

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Patient arrivals")
    rate = st.slider("Walk-in patients per hour", 1, 20, SIM_DEFAULTS["rate_per_hour"])
    hours = st.slider("Hours to simulate", 4, 24, SIM_DEFAULTS["sim_hours"])
    seed = int(st.number_input("Random seed (same seed = same patients)", 0, 9999, 42))

    st.header("Hospital resources")
    resources = {
        r: st.slider(RESOURCE_LABELS[r], 0, DEFAULT_RESOURCES[r] * 3, DEFAULT_RESOURCES[r])
        for r in RESOURCE_TYPES
    }

    st.header("Scheduling strategy")
    strategy = st.selectbox("Strategy", list(STRATEGIES), index=2)

    st.header("Scenarios")
    settings = {
        "rate_per_hour": rate,
        "sim_hours": hours,
        "surge": st.checkbox("Emergency surge (3x arrivals for 2 h)"),
        "ambulances": st.checkbox("Ambulance arrivals (+2 critical/h)"),
        "staff_shortage": st.checkbox("Staff shortage (2nd half: -2 doctors, -3 nurses)"),
        "resource_failure": st.checkbox("Equipment failure (-3 beds, -1 ICU for 90 min)"),
    }
    run_clicked = st.button("▶ Run simulation", type="primary")
