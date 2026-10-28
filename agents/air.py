"""Air mode agent: structured finding for the air leg (synthetic data only)."""


def analyze(air: dict) -> dict:
    """Build the air finding from the scenario's synthetic air slice."""
    delay = air["delay_hours"]
    status = "available" if delay < 12 else "degraded"
    return {
        "mode": "air",
        "synthetic": True,
        "status": status,
        "summary": (
            f"Air bridge {air['route']} flies above the storm; "
            f"+{delay}h delay ({air['capacity_note'].lower()})."
        ),
        "delay_hours": delay,
        "cost_usd": air["cost_usd"],
        "on_time_probability": air["on_time_probability"],
        "confidence": air["confidence"],
        "risks": ["Highest cost", "Limited cargo capacity"],
        "recommendation": "Use for the urgent portion only; too costly for full load.",
    }
