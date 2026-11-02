"""Worldwide geography: corridor presets, geocoding, station lookup.

Corridor presets are named endpoint pairs with hand-picked sea sample
points and road midpoints. Arbitrary places resolve through Nominatim
(keyless, one request per name) and rail stations through Entur's
keyless stop search; both degrade to labeled estimates when the lookup
finds nothing.
"""

import math

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "stunrazor-gridfork/1.0 (worldwide corridor lookup)"
ENTUR_URL = "https://api.entur.io/journey-planner/v3/graphql"
ENTUR_CLIENT_NAME = "stunrazor-gridfork"
STOP_SEARCH_HALF_DEG = 0.15
STOP_SEARCH_QUERY = """query {
  matches: stopPlacesByBbox(
    minimumLatitude: %(lat_min)f,
    minimumLongitude: %(lon_min)f,
    maximumLatitude: %(lat_max)f,
    maximumLongitude: %(lon_max)f
  ) {
    id
    name
    latitude
    longitude
  }
}"""

# Hand-verified presets. Sea points sit in open water between the
# endpoints; rail stops are Entur ids (None where Entur has no coverage,
# so rail honestly reports an estimated default there). Transpacific
# road/rail are inapplicable by geography (open ocean), not by outage.
CORRIDORS = {
    "north-sea": {
        "label": "Rotterdam → Oslo",
        "origin": {"name": "Rotterdam", "lat": 51.95, "lon": 4.14},
        "dest": {"name": "Oslo", "lat": 59.91, "lon": 10.75},
        "sea": {"lat": 52.0, "lon": 3.0},
        "road_mids": [{"name": "Hamburg", "lat": 53.55, "lon": 10.0}],
        "rail_stop": "NSR:StopPlace:59872",
        "rail_stop_name": "Oslo S",
        "no_road": False,
        "no_rail": False,
    },
    "skagerrak": {
        "label": "Hamburg → Oslo",
        "origin": {"name": "Hamburg", "lat": 53.55, "lon": 10.0},
        "dest": {"name": "Oslo", "lat": 59.91, "lon": 10.75},
        "sea": {"lat": 57.8, "lon": 10.0},
        "road_mids": [{"name": "Odense", "lat": 55.39, "lon": 10.38}],
        "rail_stop": "NSR:StopPlace:59872",
        "rail_stop_name": "Oslo S",
        "no_road": False,
        "no_rail": False,
    },
    "baltic": {
        "label": "Gdansk → Stockholm",
        "origin": {"name": "Gdansk", "lat": 54.35, "lon": 18.65},
        "dest": {"name": "Stockholm", "lat": 59.33, "lon": 18.07},
        "sea": {"lat": 57.5, "lon": 19.5},
        "road_mids": [{"name": "Kalmar", "lat": 56.66, "lon": 16.36}],
        "rail_stop": "NSR:StopPlace:58635",
        "rail_stop_name": "Stockholm Centralstation",
        "no_road": False,
        "no_rail": False,
    },
    "channel": {
        "label": "Rotterdam → London",
        "origin": {"name": "Rotterdam", "lat": 51.95, "lon": 4.14},
        "dest": {"name": "London", "lat": 51.51, "lon": -0.13},
        "sea": {"lat": 50.6, "lon": 1.2},
        "road_mids": [{"name": "Calais", "lat": 50.95, "lon": 1.85}],
        "rail_stop": None,
        "no_road": False,
        "no_rail": False,
    },
    "med": {
        "label": "Barcelona → Genoa",
        "origin": {"name": "Barcelona", "lat": 41.39, "lon": 2.17},
        "dest": {"name": "Genoa", "lat": 44.41, "lon": 8.93},
        "sea": {"lat": 43.0, "lon": 6.5},
        "road_mids": [{"name": "Marseille", "lat": 43.3, "lon": 5.37}],
        "rail_stop": None,
        "no_road": False,
        "no_rail": False,
    },
    "transpacific": {
        "label": "Shanghai → Los Angeles",
        "origin": {"name": "Shanghai", "lat": 31.23, "lon": 121.47},
        "dest": {"name": "Los Angeles", "lat": 34.05, "lon": -118.24},
        "sea": {"lat": 38.0, "lon": -165.0},
        "road_mids": [],
        "rail_stop": None,
        "no_road": True,
        "no_rail": True,
    },
}


def get_corridor(corridor_id: str) -> dict:
    """Return a preset by id; raises ValueError naming the known ids."""
    try:
        return CORRIDORS[corridor_id]
    except KeyError:
        known = ", ".join(sorted(CORRIDORS))
        raise ValueError(f"unknown corridor {corridor_id!r}; known: {known}")


def haversine_km(a: tuple, b: tuple) -> float:
    """Great-circle distance in km between (lat, lon) pairs."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    arc = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(
        lat2
    ) * math.sin((lon2 - lon1) / 2) ** 2
    return round(2 * 6371.0 * math.asin(math.sqrt(arc)), 1)


def midpoint(a: tuple, b: tuple) -> tuple:
    """Midpoint of two (lat, lon) pairs, rounded to two decimals."""
    return (round((a[0] + b[0]) / 2, 2), round((a[1] + b[1]) / 2, 2))


def opensky_box(lat: float, lon: float, half: float = 0.4) -> dict:
    """Small OpenSky state box around a point."""
    return {
        "lamin": round(lat - half, 2),
        "lomin": round(lon - half, 2),
        "lamax": round(lat + half, 2),
        "lomax": round(lon + half, 2),
    }


def geocode(name: str, timeout: float = 10.0) -> tuple:
    """Resolve a place name to (name, lat, lon) via Nominatim.

    Raises ValueError when nothing matches; the first result wins.
    """
    response = httpx.get(
        NOMINATIM_URL,
        params={"q": name, "format": "json", "limit": 1},
        headers={"User-Agent": NOMINATIM_USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    results = response.json()
    if not results:
        raise ValueError(f"place not found: {name!r}")
    best = results[0]
    return (name, float(best["lat"]), float(best["lon"]))


def nearest_entur_stop(lat: float, lon: float, timeout: float = 10.0):
    """Nearest Entur stop to a point as (stop_id, name), or None.

    None means no Entur coverage there (the rail leg then reports an
    estimated default); network failures also yield None rather than a
    guess, so the caller never samples the wrong station.
    """
    query = STOP_SEARCH_QUERY % {
        "lat_min": lat - STOP_SEARCH_HALF_DEG,
        "lon_min": lon - STOP_SEARCH_HALF_DEG,
        "lat_max": lat + STOP_SEARCH_HALF_DEG,
        "lon_max": lon + STOP_SEARCH_HALF_DEG,
    }
    try:
        response = httpx.post(
            ENTUR_URL,
            json={"query": query},
            headers={"ET-Client-Name": ENTUR_CLIENT_NAME},
            timeout=timeout,
        )
        response.raise_for_status()
        matches = response.json()["data"]["matches"]
    except Exception:
        return None
    best = None
    best_km = None
    for match in matches or []:
        try:
            stop = (float(match["latitude"]), float(match["longitude"]))
        except (TypeError, ValueError):
            continue
        distance = haversine_km((lat, lon), stop)
        if best_km is None or distance < best_km:
            best = (match["id"], match.get("name") or match["id"])
            best_km = distance
    return best
