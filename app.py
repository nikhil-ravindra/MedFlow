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

# ---------------------------------------------------------------------------
# Load the AI-triaged patient pool
# ---------------------------------------------------------------------------
pool, pool_error = None, None
try:
    pool = load_patient_pool()
except (FileNotFoundError, ValueError) as e:
    pool_error = str(e)

if run_clicked and pool:
    with st.spinner("Simulating the hospital with all 4 strategies..."):
        patients, events, sim_minutes, surge = prepare_run(pool, settings, seed)
        results = run_simulation(patients, resources, strategy, sim_minutes, events)
        comparison, _ = compare_strategies(patients, resources, sim_minutes, events)
        st.session_state["run"] = {
            "results": results,
            "metrics": compute_metrics(results),
            "comparison": comparison,
            "events": events,
            "surge": surge,
            "settings": dict(settings),
            "strategy": strategy,
        }
        st.session_state.pop("ai_summary", None)

run = st.session_state.get("run")

tab_live, tab_patients, tab_compare, tab_ai = st.tabs(
    ["📊 Live view", "🧑‍⚕️ Patients", "⚖️ Strategy comparison", "🤖 AI triage"]
)


def _need_run():
    if pool_error:
        st.error(pool_error)
    else:
        st.info("Choose settings in the sidebar and click **Run simulation**.")


def _shade_scenarios(fig, run):
    """Shade the surge and event windows on a time chart."""
    if run["surge"]:
        fig.add_vrect(x0=run["surge"]["start"], x1=run["surge"]["end"], fillcolor="red",
                      opacity=0.08, line_width=0, annotation_text="surge")
    seen = set()
    for e in run["events"]:
        if e["name"] in seen:
            continue
        seen.add(e["name"])
        fig.add_vrect(x0=e["start"], x1=e["end"], fillcolor="gray", opacity=0.08,
                      line_width=0, annotation_text=e["name"].lower())
    return fig


# ---------------------------------------------------------------------------
# Tab 1: Live view
# ---------------------------------------------------------------------------
with tab_live:
    if not run:
        _need_run()
    else:
        results, m = run["results"], run["metrics"]
        s = m["summary"]
        st.subheader(f"Strategy: {run['strategy']}")

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Patients arrived", s["patients"])
        c2.metric("Treated", s["treated"], f"{s['still_waiting']} still waiting", delta_color="off")
        c3.metric("Average wait", f"{s['avg_wait']:.0f} min")
        c4.metric("Seen on time", f"{s['pct_on_time']:.0f}%")
        c5.metric("Longest queue", s["max_queue"])

        # AI summary (optional second AI feature)
        if st.button("🤖 Explain these results (AI)"):
            try:
                from ai_assistant import summarize
                with st.spinner("Asking the AI analyst..."):
                    st.session_state["ai_summary"] = summarize(m, run["settings"], run["strategy"], run["events"])
            except Exception as e:  # show the problem honestly, never fake an answer
                st.session_state["ai_summary"] = f"⚠️ AI unavailable: {e}"
        if st.session_state.get("ai_summary"):
            st.info(st.session_state["ai_summary"])

        timeline = pd.DataFrame([
            {"minute": snap["t"], "queue": snap["queue_len"], "treating": snap["treating"]}
            for snap in results["timeline"]
        ])
        fig = px.line(timeline, x="minute", y=["queue", "treating"],
                      labels={"value": "patients", "variable": ""},
                      title="Patients waiting vs being treated")
        st.plotly_chart(_shade_scenarios(fig, run), width="stretch")

        util_rows = []
        for snap in results["timeline"]:
            for r in RESOURCE_TYPES:
                cap = snap["capacity"][r]
                util_rows.append({"minute": snap["t"], "resource": RESOURCE_LABELS[r],
                                  "busy %": 100 * snap["used"][r] / cap if cap else 0})
        fig = px.line(pd.DataFrame(util_rows), x="minute", y="busy %", color="resource",
                      title="Resource utilisation over time (100% = full)")
        fig.add_hline(y=100, line_dash="dash", line_color="gray")
        st.plotly_chart(_shade_scenarios(fig, run), width="stretch")

        cols = st.columns(len(RESOURCE_TYPES))
        for col, r in zip(cols, RESOURCE_TYPES):
            col.metric(f"{RESOURCE_LABELS[r]} avg busy", f"{m['utilisation'][r]:.0f}%")

        st.divider()
        st.subheader("⏱ Time travel: look inside the hospital at any minute")
        minute = st.slider("Minute", 0, results["sim_minutes"] - 1, results["sim_minutes"] // 2)
        snap = results["timeline"][minute]
        cols = st.columns(len(RESOURCE_TYPES))
        for col, r in zip(cols, RESOURCE_TYPES):
            col.metric(RESOURCE_LABELS[r], f"{snap['used'][r]} / {snap['capacity'][r]} in use")
        waiting = [
            {"ESI": f"{ESI_DOTS[p['esi']]} {p['esi']}", "id": p["id"], "complaint": p["complaint"],
             "waiting for (min)": minute - p["arrival_time"]}
            for p in results["patients"]
            if p["arrival_time"] <= minute and (p["start_time"] is None or p["start_time"] > minute)
        ]
        st.write(f"**{len(waiting)} patients waiting at minute {minute}**")
        if waiting:
            st.dataframe(pd.DataFrame(waiting).sort_values("ESI"), hide_index=True, width="stretch")

        with st.expander("🧮 Maths check: Little's law"):
            ll = m["littles_law"]
            st.markdown(
                "Queueing theory says **L = λ × W**: average number waiting = arrival rate × average wait.\n\n"
                f"- λ (arrivals per minute) = **{ll['lambda']:.3f}**\n"
                f"- W (average wait, minutes) = **{ll['W']:.1f}**\n"
                f"- Predicted L = λ × W = **{ll['L_predicted']:.2f}**\n"
                f"- Measured average queue length = **{ll['L_measured']:.2f}**\n\n"
                "They match, which shows the simulation keeps count correctly."
            )

# ---------------------------------------------------------------------------
# Tab 2: Patients
# ---------------------------------------------------------------------------
with tab_patients:
    if not run:
        _need_run()
    else:
        df = patient_table(run["results"])
        df["ESI"] = df["esi"].map(lambda e: f"{ESI_DOTS[e]} {e}")
        df["status"] = df["treated"].map({True: "treated", False: "still waiting"})
        st.dataframe(
            df[["id", "ESI", "source", "complaint", "ai_reason", "arrival_time",
                "start_time", "wait", "on_time", "status"]],
            hide_index=True, width="stretch",
        )
        df["level"] = df["esi"].map(lambda e: f"ESI {e}")
        fig = px.box(df.sort_values("esi"), x="level", y="wait", color="level",
                     color_discrete_map=ESI_COLORS, points="all",
                     title="Waiting time by urgency level (minutes)")
        st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# Tab 3: Strategy comparison
# ---------------------------------------------------------------------------
with tab_compare:
    if not run:
        _need_run()
    else:
        comp = run["comparison"]
        st.write("All four strategies were run on **exactly the same patients**, so the comparison is fair.")
        st.dataframe(comp, hide_index=True, width="stretch")

        wait_cols = [f"ESI {e} avg wait" for e in ESI]
        long = comp.melt(id_vars="strategy", value_vars=wait_cols, var_name="level", value_name="avg wait (min)")
        long["level"] = long["level"].str.replace(" avg wait", "")
        fig = px.bar(long, x="level", y="avg wait (min)", color="strategy", barmode="group",
                     title="Average wait per urgency level")
        st.plotly_chart(fig, width="stretch")

        max_cols = [f"ESI {e} max wait" for e in ESI]
        long = comp.melt(id_vars="strategy", value_vars=max_cols, var_name="level", value_name="max wait (min)")
        long["level"] = long["level"].str.replace(" max wait", "")
        fig = px.bar(long, x="level", y="max wait (min)", color="strategy", barmode="group",
                     title="Worst-case wait per urgency level (fairness)")
        st.plotly_chart(fig, width="stretch")

        fig = px.bar(comp, x="strategy", y="pct_on_time", color="strategy",
                     title="% of patients seen within their target time")
        st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# Tab 4: AI triage (live - proves the AI is real)
# ---------------------------------------------------------------------------
with tab_ai:
    st.subheader("AI triage nurse")
    st.write("Type any patient complaint. The LLM assigns an urgency level (ESI 1–5) and the resources needed.")
    text = st.text_area("Patient complaint and vital signs",
                        "Severe headache, blurred vision, BP 190/110, age 58")
    if st.button("Triage with AI"):
        try:
            with st.spinner("Asking the AI..."):
                r = triage(text, use_cache=False)
            info = ESI[r["esi"]]
            st.markdown(f"### {ESI_DOTS[r['esi']]} ESI {r['esi']} — {info['name']}")
            st.write(f"**Reason:** {r['reason']}")
            st.write(f"**Should be seen within:** {info['target_wait']} min")
            st.write("**Resources needed:** " + ", ".join(
                f"{n} × {RESOURCE_LABELS[k]}" for k, n in r["needs"].items() if n))
            st.caption(f"Model: {r['model']}")
        except TriageError as e:
            st.error(f"AI unavailable: {e}")

    with st.expander("What do the ESI levels mean?"):
        st.dataframe(pd.DataFrame([
            {"ESI": f"{ESI_DOTS[k]} {k}", "name": v["name"], "example": v["example"],
             "target wait (min)": v["target_wait"],
             "treatment (min)": f"{v['treatment_minutes'][0]}–{v['treatment_minutes'][1]}"}
            for k, v in ESI.items()
        ]), hide_index=True, width="stretch")





















