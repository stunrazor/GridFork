"""Rail mode agent: structured finding for the rail leg (synthetic data only)."""


def analyze(rail: dict) -> dict:
    """Build the rail finding from the scenario's synthetic rail slice."""
    delay = rail["delay_hours"]
    status = "available" if delay < 12 else "degraded"
    return {
        "mode": "rail",
        "synthetic": True,
        "status": status,
        "summary": (
            f"Intermodal {rail['route']} ({rail['transit_hours']}h transit); "
            f"+{delay}h delay from wind speed restrictions."
        ),
        "delay_hours": delay,
        "cost_usd": rail["cost_usd"],
        "on_time_probability": rail["on_time_probability"],
        "confidence": rail["confidence"],
        "risks": ["Single-corridor congestion", "Last-mile handling in Oslo"],
        "recommendation": "Best balanced full-load reroute; book corridor slot early.",
    }
