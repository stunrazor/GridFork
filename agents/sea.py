"""Sea mode agent: structured finding for the ocean leg (synthetic data only)."""


def analyze(sea: dict) -> dict:
    """Build the sea finding from the scenario's synthetic sea slice."""
    delay = sea["delay_hours"]
    if sea["wave_height_m"] >= 8 or sea["wind_kph"] >= 100:
        status = "disrupted"
    elif delay >= 12:
        status = "degraded"
    else:
        status = "available"
    return {
        "mode": "sea",
        "synthetic": True,
        "status": status,
        "summary": (
            f"Direct sailing {sea['route']} blocked by storm "
            f"({sea['wave_height_m']}m waves, {sea['wind_kph']}kph wind); "
            f"{sea['port_status'].lower()}, +{delay}h delay."
        ),
        "delay_hours": delay,
        "cost_usd": sea["cost_usd"],
        "on_time_probability": sea["on_time_probability"],
        "confidence": sea["confidence"],
        "risks": ["Storm damage risk", "Port closure extension"],
        "recommendation": "Do not sail; consider only as wait-and-see fallback.",
    }
