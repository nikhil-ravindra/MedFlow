# MedFlow — Prioritize Patients. Optimize Resources.

A hospital resource management simulator built for **Hack-a-Matics 2026** (Theme: VECTOR, problem statement: MedFlow).

Patients arrive at random. An **AI triage nurse (LLM)** reads each patient's complaint and assigns an urgency level and the resources they need. A minute-by-minute simulation then allocates beds, ICU beds, doctors and nurses using one of four scheduling strategies, and a dashboard shows waiting times, utilisation and a fair side-by-side comparison of the strategies.

**Pipeline:** Patient arrivals → AI priority calculation → Resource allocation → Scheduling simulation → Performance statistics

## Features

- Patients with 5 urgency levels (ESI, the standard Emergency Severity Index)
- A waiting queue, resource tracking, and all-or-nothing allocation, so two patients never share a bed and capacity is never exceeded
- 4 scheduling strategies, compared on the **same** patients
- Operations dashboard: live charts, a time-travel slider, and a patient table
- Scenarios (bonus features): emergency surge, ambulance arrivals, staff shortage, equipment failure, ICU capacity
- AI triage (live) and an AI results analyst

##  AI component

| What | How |
|---|---|
| **AI triage** (`triage.py`) | Google Gemini (default `gemini-2.5-flash`, set with `GEMINI_MODEL`) receives the patient's free-text complaint and vital signs, plus the ESI definitions. It returns JSON: ESI level 1–5, the resources needed (bed, ICU bed, doctors, nurses) and a one-line reason. The answer is validated: ESI must be 1–5, resource counts are limited to sensible ranges, and every patient gets at least 1 doctor. |
| **Patient pool** (`build_dataset.py`) | Every complaint in `data/complaints.txt` goes through the AI triage **once**. The results are saved to `data/patients.json`, and the simulation draws patients from this file. Replies are cached in `data/triage_cache.json` to save API quota. |
| **Live triage tab** | In the dashboard's "AI triage" tab, anyone can type a new complaint and see the model classify it live, with no cache. |
| **AI analyst** (`ai_assistant.py`) | After a simulation run, the metrics are sent to Gemini, which explains the main bottleneck and gives one recommendation. |

Nothing is hardcoded. If the API is unavailable, the app shows "AI unavailable" instead of a made-up answer.

##  The maths

1. **Random arrivals (Poisson process):** For each simulated minute, the number of new patients follows a Poisson distribution with mean λ = rate / 60. A surge multiplies λ by 3 for 2 hours. Ambulances are a second Poisson stream of ESI 1–2 patients.
2. **Discrete-time simulation:** Each minute, finished patients are discharged, new arrivals join the queue, and the strategy orders the queue.
3. **All-or-nothing allocation:** A patient starts treatment only if **every** resource they need is free, and then takes all of them at once. This rules out resource conflicts and capacity violations. The tests in `tests/` check this for every minute.
4. **Scheduling strategies:**
   - *First come, first served:* ordered by arrival time.
   - *Urgency only:* lowest ESI first.
   - *Urgency + shortest job first:* the classic rule that minimises average waiting time.
   - *Urgency + waiting time (ours):* critical patients (ESI 1–2) always go first. Everyone else is ordered by **lateness = minutes waited ÷ target wait for their ESI level**. This protects critical patients as well as "urgency only" does, while stopping low-urgency patients from waiting forever (no starvation).
5. **Fair comparison:** Every strategy is run on the exact same list of patients, generated with the same random seed.
6. **Validation with Little's law (L = λW):** The simulation's measured average queue length matches λ × W exactly. This is checked in the tests and shown in the dashboard.

## Findings

On a normal day all strategies perform the same (≈1 min average wait, 94.5% seen on time): the hospital has spare capacity.
During a surge, first-come-first-served makes life-threatening ESI 1 patients wait 41 min on average; every urgency-based strategy cuts this to about 6 min.
Urgency-only leaves the lowest-priority patients waiting up to 457 min. Our strategy cuts the worst case to 289 min (−37%) while also slightly improving ESI 1–2 waits (6.0 vs 6.5 min, 11.4 vs 13.6 min).
Trade-off: shortest-job-first sees the most patients within their target (58% vs our 43%), because it clears quick cases first. Our strategy prioritises fairness (no one waits forever) over that metric.

## How to run

```bash
git clone <this repo> && cd medflow
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export GEMINI_API_KEY="your-key"          # free key from Google AI Studio (Windows: set GEMINI_API_KEY=...)
python build_dataset.py                    # AI-triages data/complaints.txt -> data/patients.json (one time)
streamlit run app.py                       # open the dashboard
python -m pytest                           # run the tests
```

If Google has retired the default model, set `export GEMINI_MODEL="<current flash model name>"`.

## Project structure

| File | What it does | Owner |
|---|---|---|
| `config.py` | Shared settings: resources, ESI table, scenarios | Vansh |
| `sim.py` | Arrivals, events and the minute-by-minute simulation | Vansh |
| `strategies.py` | The 4 scheduling strategies | Om |
| `metrics.py` | Waiting times, % seen on time, utilisation, Little's law, strategy comparison | Om |
| `tests/test_sim.py` | Checks capacity, fairness and Little's law | Om |
| `app.py` | Streamlit dashboard | Dwijesh |
| `triage.py`, `ai_assistant.py`, `build_dataset.py`, `data/` | AI components and data | Nikhil |

## Simplifications

- A "doctor" or "nurse" is one staff slot that stays with a patient for the whole treatment.
- Treatment times are drawn uniformly from a range for each ESI level (see `config.py`).
- The patient complaints are fictional.

## Disclosures

- **Libraries:** Streamlit, pandas, Plotly, google-genai, pytest.
- **AI assistance:** AI coding assistants (Claude, ChatGPT) helped write code, and AI helped draft the example complaints in `data/complaints.txt`. The design, the scheduling logic, the integration and the testing are the team's own work.

## Team

-  vansh
-  om
-  dwijesh
-  nikhil























