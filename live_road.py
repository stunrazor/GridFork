"""Phase 2 road layer: live corridor congestion from TomTom Traffic Flow.

A free TomTom key is required: register at https://developer.tomtom.com
(no payment method) and set TOMTOM_API_KEY. Without it,
``fetch_corridor_congestion`` reports ``setup-required`` and performs no
network call.
"""

import os

import httpx

FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
# One sample per corridor leg: origin, midpoint, approach.
POINTS = (
    ("Rotterdam", 51.95, 4.14),
    ("Hamburg", 53.55, 10.0),
    ("Oslo approach", 59.85, 10.65),
)
SETUP_DETAIL = (
    "Free TomTom key needed: set TOMTOM_API_KEY from "
    "https://developer.tomtom.com. The road leg stays synthetic until then."
)


def fetch_corridor_congestion(timeout: float = 10.0) -> dict:
    """Return live congestion ratios, setup-required, or a fallback.

    Each point reports current speed as a ratio of free-flow speed; the
    worst (lowest) ratio drives the road leg. Live with at least one
    usable point; a total failure falls back labeled.
    """
    api_key = (os.environ.get("TOMTOM_API_KEY") or "").strip()
    if not api_key:
        return {
            "source": "setup-required",
            "live": False,
            "worst_ratio": None,
            "points": [],
            "observed_at": None,
            "detail": SETUP_DETAIL,
        }
    try:
        points = []
        for label, lat, lon in POINTS:
            response = httpx.get(
                FLOW_URL,
                params={"point": f"{lat},{lon}", "key": api_key},
                timeout=timeout,
            )
            response.raise_for_status()
            segment = response.json()["flowSegmentData"]
            free = float(segment["freeFlowSpeed"])
            if free <= 0:
                continue
            points.append(
                {
                    "label": label,
                    "ratio": round(float(segment["currentSpeed"]) / free, 3),
                }
            )
        if not points:
            raise ValueError("no usable flow segments")
        return {
            "source": "tomtom",
            "live": True,
            "worst_ratio": min(p["ratio"] for p in points),
            "points": points,
            # Flow segments are real-time with no timestamp in the payload.
            "observed_at": None,
        }
    except Exception:
        return {
            "source": "synthetic-fallback",
            "live": False,
            "worst_ratio": None,
            "points": [],
            "observed_at": None,
        }
