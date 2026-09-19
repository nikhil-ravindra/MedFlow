# 🏥 MedFlow — Prioritize Patients. Optimize Resources.

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
