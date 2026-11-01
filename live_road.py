"""Phase 2 road layer: live congestion, incidents, and routed transit.

A free TomTom key is required: register at https://developer.tomtom.com
(no payment method), enable the Traffic and Routing products, and set
TOMTOM_API_KEY. Without it, ``fetch_corridor_congestion`` reports
``setup-required`` and performs no network call.

One snapshot costs up to 7 calls: 3 flow segments, 3 incident boxes, and
1 truck route. Flow is the base layer: incidents and routing only ever
raise the delay estimate, never lower it.
"""

import os

import httpx

FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
INCIDENTS_URL = "https://api.tomtom.com/traffic/services/5/incidentDetails"
INCIDENT_FIELDS = (
    "{incidents{properties{id,iconCategory,magnitudeOfDelay,events{description}}}}"
)
ROUTING_URL = "https://api.tomtom.com/routing/1/calculateRoute/{origin}:{dest}/json"
ROUTE_ORIGIN = (51.95, 4.14)  # Rotterdam
ROUTE_DEST = (59.91, 10.75)  # Oslo
# One sample per corridor leg: origin, midpoint, approach.
POINTS = (
    ("Rotterdam", 51.95, 4.14),
    ("Hamburg", 53.55, 10.0),
    ("Oslo approach", 59.85, 10.65),
)
INCIDENT_HALF_DEG = 0.35
# iconCategory 8 = road closed; magnitudeOfDelay 3/4 = major/closure.
CLOSURE_CATEGORY = 8
MAJOR_MAGNITUDES = (3, 4)
SETUP_DETAIL = (
    "Free TomTom key needed: set TOMTOM_API_KEY from "
    "https://developer.tomtom.com (enable the Traffic and Routing "
    "products). The road leg stays synthetic until then."
)


def _fetch_flow(api_key: str, timeout: float) -> list[dict]:
    """Current/free-flow ratios per sample point; raises if none usable."""
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
    return points


def _severity(value) -> int | None:
    """Coerce a category/magnitude code to int; None when unparseable."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _fetch_incidents(api_key: str, timeout: float) -> dict | None:
    """Aggregate live incidents over the sample boxes; None if all fail."""
    count = 0
    closures = 0
    majors = 0
    sample: list[str] = []
    boxes_ok = 0
    for _, lat, lon in POINTS:
        try:
            response = httpx.get(
                INCIDENTS_URL,
                params={
                    "key": api_key,
                    "bbox": (
                        f"{lon - INCIDENT_HALF_DEG},{lat - INCIDENT_HALF_DEG},"
                        f"{lon + INCIDENT_HALF_DEG},{lat + INCIDENT_HALF_DEG}"
                    ),
                    "fields": INCIDENT_FIELDS,
                    "language": "en-US",
                    "timeValidityFilter": "present",
                },
                timeout=timeout,
            )
            response.raise_for_status()
            incidents = response.json().get("incidents", [])
            boxes_ok += 1
        except Exception:
            continue
        for incident in incidents:
            props = incident.get("properties", {})
            count += 1
            if _severity(props.get("iconCategory")) == CLOSURE_CATEGORY:
                closures += 1
            if _severity(props.get("magnitudeOfDelay")) in MAJOR_MAGNITUDES:
                majors += 1
            events = props.get("events", [])
            if events and len(sample) < 3:
                sample.append(str(events[0].get("description", "")))
    if not boxes_ok:
        return None
    return {
        "count": count,
        "closures": closures,
        "majors": majors,
        "sample": sample,
    }


def _fetch_route(api_key: str, timeout: float) -> dict | None:
    """Routed truck transit Rotterdam-Oslo; None on any failure."""
    try:
        origin = f"{ROUTE_ORIGIN[0]},{ROUTE_ORIGIN[1]}"
        dest = f"{ROUTE_DEST[0]},{ROUTE_DEST[1]}"
        response = httpx.get(
            ROUTING_URL.format(origin=origin, dest=dest),
            params={"key": api_key, "traffic": "true", "travelMode": "truck"},
            timeout=timeout,
        )
        response.raise_for_status()
        summary = response.json()["routes"][0]["summary"]
        return {
            "distance_km": round(summary["lengthInMeters"] / 1000),
            "transit_hours": round(summary["travelTimeInSeconds"] / 3600, 1),
            "traffic_delay_hours": round(
                summary["trafficDelayInSeconds"] / 3600, 1
            ),
        }
    except Exception:
        return None


def fetch_corridor_congestion(timeout: float = 10.0) -> dict:
    """Return live road data, setup-required, or a fallback.

    Each point reports current speed as a ratio of free-flow speed; the
    worst (lowest) ratio drives the road leg. Live with at least one
    usable flow point; the incident and route blocks attach when their
    calls succeed and are None otherwise.
    """
    api_key = (os.environ.get("TOMTOM_API_KEY") or "").strip()
    if not api_key:
        return {
            "source": "setup-required",
            "live": False,
            "worst_ratio": None,
            "points": [],
            "incidents": None,
            "route": None,
            "observed_at": None,
            "detail": SETUP_DETAIL,
        }
    try:
        points = _fetch_flow(api_key, timeout)
        return {
            "source": "tomtom",
            "live": True,
            "worst_ratio": min(p["ratio"] for p in points),
            "points": points,
            "incidents": _fetch_incidents(api_key, timeout),
            "route": _fetch_route(api_key, timeout),
            # Flow/incident/route payloads carry no usable global timestamp.
            "observed_at": None,
        }
    except Exception:
        return {
            "source": "synthetic-fallback",
            "live": False,
            "worst_ratio": None,
            "points": [],
            "incidents": None,
            "route": None,
            "observed_at": None,
        }
