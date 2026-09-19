"""
ai_assistant.py - second AI feature: explains simulation results in plain English.

Owner: Nikhil
"""

from triage import ask_gemini


def summarize(metrics, settings, strategy_name, events):
    """Ask the LLM for a short explanation of the bottleneck + one recommendation."""
    s = metrics["summary"]
    by_esi = metrics["by_esi"]
    esi_lines = "\n".join(
        f"- ESI {int(row.esi)}: {int(row.patients)} patients, avg wait {row.avg_wait:.0f} min, "
        f"max wait {row.max_wait:.0f} min, {row.pct_on_time:.0f}% seen within target "
        f"({int(row.target_wait)} min)"
        for row in by_esi.itertuples()
    )
    util_lines = "\n".join(f"- {r}: {u:.0f}% busy on average" for r, u in metrics["utilisation"].items())
    event_lines = "\n".join(
        f"- {e['name']}: {e['resource']} {e['delta']:+d} from minute {e['start']} to {e['end']}"
        for e in events
    ) or "- none"
    scenarios = [k for k in ("surge", "staff_shortage", "resource_failure", "ambulances") if settings.get(k)]

    prompt = f"""You are a hospital operations analyst. Here are the results of an
emergency department simulation ({settings['sim_hours']} hours, about
{settings['rate_per_hour']} walk-in patients per hour, strategy: {strategy_name},
scenarios: {', '.join(scenarios) or 'normal day'}).

Overall: {s['patients']} patients arrived, {s['treated']} treated, {s['still_waiting']} still waiting,
average wait {s['avg_wait']:.0f} min, {s['pct_on_time']:.0f}% seen within their target time,
average queue {s['avg_queue']:.1f}, longest queue {s['max_queue']}.

By urgency level:
{esi_lines}

Resource utilisation:
{util_lines}

Capacity events:
{event_lines}

In at most 4 short sentences, plain English, no bullet points: name the main
bottleneck resource, say which patients suffered most, and give ONE concrete
recommendation (for example how many of which resource to add). Use the numbers."""
    return ask_gemini(prompt, json_mode=False, temperature=0.3).strip()
