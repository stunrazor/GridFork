"""Road mode agent: structured finding for the road leg (synthetic data only)."""


def analyze(road: dict) -> dict:
    """Build the road finding from the scenario's synthetic road slice."""
    delay = road["delay_hours"]
    status = "available" if delay < 12 else "degraded"
    return {
        "mode": "road",
        "synthetic": True,
        "status": status,
        "summary": (
            f"Truck {road['route']} ({road['distance_km']}km, "
            f"{road['transit_hours']}h transit); +{delay}h delay from "
            "bridge wind restrictions."
        ),
        "delay_hours": delay,
        "cost_usd": road["cost_usd"],
        "on_time_probability": road["on_time_probability"],
        "confidence": road["confidence"],
        "risks": ["Bridge closures in gusts", "Driver hours limits"],
        "recommendation": "Viable full-load fallback; monitor bridge status.",
    }
