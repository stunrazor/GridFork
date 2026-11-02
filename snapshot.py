"""Worldwide snapshots: a live four-mode ranking for any corridor.

The same deterministic engine as the demo (delay rules, agents, scoring)
runs against live clients pointed at the corridor's endpoints. Costs,
on-time probabilities, and confidences stay synthetic estimates — no
free real-time source exists — and per-field provenance says so. Legs
that cannot apply (open-ocean road/rail) are excluded from the ranking
with a reason instead of a silent guess.
"""

import geo
import live_air
import live_marine
import live_rail
import live_road
import live_weather
import orchestrator

DEFAULT_DELAY_HOURS = 6
SEA_SPEED_KMH = 35.0
SEA_DETOUR = 1.15
AIR_SPEED_KMH = 750.0
AIR_HANDLING_HOURS = 2.0
ROAD_SPEED_KMH = 70.0
ROAD_DETOUR = 1.25
RAIL_SPEED_KMH = 60.0
RAIL_HANDLING_HOURS = 2.0
RAIL_DETOUR = 1.2
COST_PER_KM = {"sea": 1.2, "rail": 2.0, "road": 3.5, "air": 12.0}
LIVE_CONFIDENCE = 0.85
DEFAULT_CONFIDENCE = 0.6
OCEAN_REASON = "Open ocean between endpoints: no road link exists."
OCEAN_RAIL_REASON = "Open ocean between endpoints: no rail link exists."

MODE_ORDER = ("sea", "air", "road", "rail")


def _on_time(delay_hours: float) -> float:
    """Deterministic on-time estimate from delay hours."""
    return round(min(0.98, max(0.3, 0.95 - 0.015 * delay_hours)), 4)


def _confidence(delay_provenance: str) -> float:
    """Higher confidence when live conditions set the delay."""
    if delay_provenance == "estimated-from-conditions":
        return LIVE_CONFIDENCE
    return DEFAULT_CONFIDENCE


def _not_applicable(mode: str, reason: str) -> dict:
    """Leg/readout pair for a geographically impossible leg."""
    return {
        "mode": mode,
        "applicable": False,
        "live": False,
        "status": "unavailable",
        "reason": reason,
        "delay_hours": None,
        "transit_hours": None,
    }


def build_snapshot(
    origin: dict,
    dest: dict,
    label: str,
    sea: dict | None = None,
    road_mids: tuple = (),
    rail_stop: str | None = None,
    rail_stop_name: str | None = None,
    no_road: bool = False,
    no_rail: bool = False,
    timeout: float = 10.0,
) -> dict:
    """Rank every applicable mode live for one origin/dest pair.

    ``origin``/``dest``/``sea`` are ``{"name", "lat", "lon"}`` dicts (sea
    needs only lat/lon); ``sea`` defaults to the endpoint midpoint and
    ``road_mids`` to the same midpoint. ``rail_stop`` is an Entur stop
    id; without one the destination's nearest stop is looked up, and
    without coverage rail honestly reports an estimated default.
    """
    o = (origin["lat"], origin["lon"])
    d = (dest["lat"], dest["lon"])
    distance = geo.haversine_km(o, d)
    sea_pt = (sea["lat"], sea["lon"]) if sea else geo.midpoint(o, d)
    route_label = f"{origin['name']}–{dest['name']}"
    legs: dict = {}
    slices: dict = {}
    provenance: dict = {}
    readouts: dict = {}

    # Sea: waves at the sea point, wind at the origin port.
    sea_dist = round(distance * SEA_DETOUR, 1)
    sea_transit = round(sea_dist / SEA_SPEED_KMH, 1)
    marine = live_marine.fetch_waves_at(sea_pt[0], sea_pt[1], timeout=timeout)
    wind = live_weather.fetch_wind_at(o[0], o[1], timeout=timeout)
    readouts["marine"], readouts["wind"] = marine, wind
    sea_live = marine["live"] or wind["live"]
    if sea_live:
        delay, port_status = orchestrator._sea_conditions_to_delay(
            marine["wave_height_m"], wind["wind_kph"], port=origin["name"]
        )
        delay_prov = "estimated-from-conditions"
    else:
        delay, port_status = DEFAULT_DELAY_HOURS, (
            f"{origin['name']} departures unknown"
        )
        delay_prov = "estimated-default"
    legs["sea"] = {
        "mode": "sea",
        "applicable": True,
        "live": sea_live,
        "delay_hours": delay,
        "transit_hours": sea_transit,
        "delay_provenance": delay_prov,
        "wave_height_m": marine["wave_height_m"],
        "wind_kph": wind["wind_kph"],
        "marine_source": marine["source"],
        "wind_source": wind["source"],
    }
    slices["sea"] = {
        "route": route_label,
        "wave_height_m": marine["wave_height_m"],
        "wind_kph": wind["wind_kph"],
        "port_status": port_status,
        "delay_hours": delay,
        "transit_hours": sea_transit,
        "cost_usd": round(sea_dist * COST_PER_KM["sea"]),
        "on_time_probability": _on_time(delay),
        "confidence": _confidence(delay_prov),
    }
    provenance["sea"] = {
        "wave_height_m": "measured" if marine["live"] else "synthetic-fallback",
        "wind_kph": "measured" if wind["live"] else "synthetic-fallback",
        "delay_hours": delay_prov,
        "port_status": delay_prov,
        "cost_usd": "synthetic-estimate",
        "on_time_probability": "synthetic-estimate",
        "confidence": "synthetic-estimate",
    }

    # Air: traffic near both endpoints, OpenSky then keyless adsb.lol.
    air_dist = distance
    air_transit = round(air_dist / AIR_SPEED_KMH + AIR_HANDLING_HOURS, 1)
    air = live_air.fetch_air_traffic(
        timeout=timeout,
        boxes=(
            ("origin", geo.opensky_box(*o)),
            ("dest", geo.opensky_box(*d)),
        ),
        points=(("origin", o), ("dest", d)),
    )
    readouts["air"] = air
    if air["live"]:
        total = air["airborne_origin"] + air["airborne_dest"]
        delay = orchestrator._observed_traffic_to_air_delay(total)
        if delay is None:
            delay, delay_prov = DEFAULT_DELAY_HOURS, "estimated-default"
        else:
            delay_prov = "estimated-from-conditions"
    else:
        total = None
        delay, delay_prov = DEFAULT_DELAY_HOURS, "estimated-default"
    legs["air"] = {
        "mode": "air",
        "applicable": True,
        "live": air["live"],
        "delay_hours": delay,
        "transit_hours": air_transit,
        "delay_provenance": delay_prov,
        "airborne_origin": air.get("airborne_origin"),
        "airborne_dest": air.get("airborne_dest"),
        "source": air["source"],
    }
    slices["air"] = {
        "route": route_label,
        "capacity_note": (
            f"{total} contacts near endpoints" if total is not None
            else "Coverage unknown"
        ),
        "delay_hours": delay,
        "transit_hours": air_transit,
        "cost_usd": round(air_dist * COST_PER_KM["air"]),
        "on_time_probability": _on_time(delay),
        "confidence": _confidence(delay_prov),
    }
    provenance["air"] = {
        "airborne_origin": "measured" if air["live"] else "unavailable",
        "airborne_dest": "measured" if air["live"] else "unavailable",
        "delay_hours": delay_prov,
        "cost_usd": "synthetic-estimate",
        "on_time_probability": "synthetic-estimate",
        "confidence": "synthetic-estimate",
    }

    # Road: corridor flow, incidents, and a routed truck transit.
    if no_road:
        legs["road"] = _not_applicable("road", OCEAN_REASON)
        readouts["road"] = {"source": "not-applicable", "live": False}
        provenance["road"] = {"delay_hours": "not-applicable"}
    else:
        mids = list(road_mids) or [
            {"name": "Corridor midpoint", "lat": mid[0], "lon": mid[1]}
            for mid in [geo.midpoint(o, d)]
        ]
        points = (
            (origin["name"], o[0], o[1]),
            *((m["name"], m["lat"], m["lon"]) for m in mids),
            (dest["name"], d[0], d[1]),
        )
        road = live_road.fetch_corridor_congestion(
            timeout=timeout, points=points, origin=o, dest=d
        )
        readouts["road"] = road
        if road["live"]:
            delay = orchestrator._congestion_to_road_delay(road["worst_ratio"])
            delay = max(delay, orchestrator._road_incident_floor(road))
            route = road.get("route") or {}
            road_dist = route.get("distance_km", round(distance * ROAD_DETOUR, 1))
            road_transit = route.get(
                "transit_hours", round(road_dist / ROAD_SPEED_KMH + 1, 1)
            )
            delay = max(delay, round(route.get("traffic_delay_hours", 0)))
            delay_prov = "estimated-from-conditions"
        else:
            road_dist = round(distance * ROAD_DETOUR, 1)
            road_transit = round(road_dist / ROAD_SPEED_KMH + 1, 1)
            delay, delay_prov = DEFAULT_DELAY_HOURS, "estimated-default"
        legs["road"] = {
            "mode": "road",
            "applicable": True,
            "live": road["live"],
            "delay_hours": delay,
            "transit_hours": road_transit,
            "delay_provenance": delay_prov,
            "worst_ratio": road.get("worst_ratio"),
            "incidents": road.get("incidents"),
            "route": road.get("route"),
            "source": road["source"],
        }
        slices["road"] = {
            "route": route_label,
            "distance_km": road_dist,
            "transit_hours": road_transit,
            "delay_hours": delay,
            "cost_usd": round(road_dist * COST_PER_KM["road"]),
            "on_time_probability": _on_time(delay),
            "confidence": _confidence(delay_prov),
        }
        provenance["road"] = {
            "worst_congestion_ratio": (
                "measured" if road["live"] else "unavailable"
            ),
            "delay_hours": delay_prov,
            "cost_usd": "synthetic-estimate",
            "on_time_probability": "synthetic-estimate",
            "confidence": "synthetic-estimate",
        }

    # Rail: departures at the corridor stop, keyless via Entur.
    if no_rail:
        legs["rail"] = _not_applicable("rail", OCEAN_RAIL_REASON)
        readouts["rail"] = {"source": "not-applicable", "live": False}
        provenance["rail"] = {"delay_hours": "not-applicable"}
    else:
        rail_dist = round(distance * RAIL_DETOUR, 1)
        rail_transit = round(rail_dist / RAIL_SPEED_KMH + RAIL_HANDLING_HOURS, 1)
        stop_id, stop_name = rail_stop, rail_stop_name or rail_stop
        if stop_id is None:
            try:
                resolved = geo.nearest_entur_stop(d[0], d[1], timeout=timeout)
            except Exception:
                resolved = None
            if resolved is not None:
                stop_id, stop_name = resolved
        if stop_id is None:
            rail = {"source": "no-coverage", "live": False}
            delay, delay_prov = DEFAULT_DELAY_HOURS, "estimated-default"
            detail = f"No Entur rail coverage near {dest['name']}"
        else:
            rail = live_rail.fetch_entur_disruptions(
                timeout=timeout, stop_id=stop_id
            )
            if rail["live"]:
                delay = orchestrator._disruptions_to_rail_delay(
                    rail["active_count"], rail["severe_count"]
                )
                delay_prov = "estimated-from-conditions"
            else:
                delay, delay_prov = DEFAULT_DELAY_HOURS, "estimated-default"
            detail = f"Sampled departures at {stop_name}"
        readouts["rail"] = rail
        legs["rail"] = {
            "mode": "rail",
            "applicable": True,
            "live": rail["live"],
            "delay_hours": delay,
            "transit_hours": rail_transit,
            "delay_provenance": delay_prov,
            "stop_id": stop_id,
            "stop_name": stop_name,
            "active_count": rail.get("active_count"),
            "severe_count": rail.get("severe_count"),
            "detail": detail,
        }
        slices["rail"] = {
            "route": route_label,
            "transit_hours": rail_transit,
            "delay_hours": delay,
            "cost_usd": round(rail_dist * COST_PER_KM["rail"]),
            "on_time_probability": _on_time(delay),
            "confidence": _confidence(delay_prov),
        }
        provenance["rail"] = {
            "active_disruptions": "measured" if rail["live"] else "unavailable",
            "delay_hours": delay_prov,
            "cost_usd": "synthetic-estimate",
            "on_time_probability": "synthetic-estimate",
            "confidence": "synthetic-estimate",
        }

    # Inapplicable legs still need slices for the shared agents; their
    # findings are filtered out of the response below.
    if "road" not in slices:
        slices["road"] = {
            "route": route_label,
            "distance_km": 0,
            "transit_hours": 0,
            "delay_hours": DEFAULT_DELAY_HOURS,
            "cost_usd": 0,
            "on_time_probability": 0.0,
            "confidence": 0.0,
        }
    if "rail" not in slices:
        slices["rail"] = {
            "route": route_label,
            "transit_hours": 0,
            "delay_hours": DEFAULT_DELAY_HOURS,
            "cost_usd": 0,
            "on_time_probability": 0.0,
            "confidence": 0.0,
        }
    findings = {
        finding["mode"]: finding
        for finding in orchestrator.collect_findings({"modes": slices})
        if finding["mode"] in legs and legs[finding["mode"]].get("applicable", True)
    }
    for mode, finding in findings.items():
        legs[mode]["status"] = finding["status"]
    applicable = [mode for mode in MODE_ORDER if mode in findings]
    baseline = max(findings[mode]["delay_hours"] for mode in applicable)
    options = [
        {
            "option_id": f"{mode}-leg",
            "title": f"{mode.capitalize()} · {label}",
            "mode": mode,
            "cost_usd": findings[mode]["cost_usd"],
            "time_saved_hours": baseline - findings[mode]["delay_hours"],
            "on_time_probability": findings[mode]["on_time_probability"],
            "confidence": findings[mode]["confidence"],
        }
        for mode in applicable
    ]
    ranked = orchestrator.score_options(options)
    fastest = min(
        applicable,
        key=lambda mode: (
            legs[mode]["transit_hours"] + legs[mode]["delay_hours"],
            MODE_ORDER.index(mode),
        ),
    )
    return {
        "corridor": None,
        "label": label,
        "endpoints": {"origin": origin, "dest": dest},
        "distance_km": distance,
        "legs": legs,
        "marine": readouts["marine"],
        "wind": readouts["wind"],
        "air": readouts["air"],
        "road": readouts["road"],
        "rail": readouts["rail"],
        "provenance": provenance,
        "findings": [findings[mode] for mode in applicable],
        "ranked_options": ranked,
        "fastest_alternative": {
            "mode": fastest,
            "option_id": f"{fastest}-leg",
            "total_hours": round(
                legs[fastest]["transit_hours"] + legs[fastest]["delay_hours"], 1
            ),
            "transit_hours": legs[fastest]["transit_hours"],
            "delay_hours": legs[fastest]["delay_hours"],
        },
    }


def snapshot_for_corridor(corridor_id: str, timeout: float = 10.0) -> dict:
    """Build a snapshot for a preset corridor id."""
    preset = geo.get_corridor(corridor_id)
    snap = build_snapshot(
        preset["origin"],
        preset["dest"],
        preset["label"],
        sea=preset["sea"],
        road_mids=tuple(preset["road_mids"]),
        rail_stop=preset["rail_stop"],
        rail_stop_name=preset.get("rail_stop_name"),
        no_road=preset["no_road"],
        no_rail=preset["no_rail"],
        timeout=timeout,
    )
    snap["corridor"] = corridor_id
    return snap


def snapshot_for_places(
    origin_name: str, dest_name: str, timeout: float = 10.0
) -> dict:
    """Build a snapshot for two geocoded place names."""
    origin = geo.geocode(origin_name, timeout=timeout)
    dest = geo.geocode(dest_name, timeout=timeout)
    return build_snapshot(
        {"name": origin[0], "lat": origin[1], "lon": origin[2]},
        {"name": dest[0], "lat": dest[1], "lon": dest[2]},
        f"{origin[0]} → {dest[0]}",
        timeout=timeout,
    )
