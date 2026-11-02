"""Live wave layer: current North Sea wave height from Open-Meteo Marine.

Keyless like the wind layer: ``GET /v1/marine`` with latitude/longitude
returns JSON with ``current.wave_height`` in meters. The coordinates are
open water off Rotterdam on the demo route. Any failure falls back to a
clearly labeled synthetic value so the demo keeps working offline.
"""

import httpx

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
LATITUDE = 52.0
LONGITUDE = 3.0
# Matches the synthetic storm slice; used only when clearly labeled fallback.
FALLBACK_WAVE_HEIGHT_M = 8.5


def fetch_north_sea_waves(timeout: float = 10.0) -> dict:
    """Return the live wave readout, or a labeled synthetic fallback."""
    return fetch_waves_at(LATITUDE, LONGITUDE, timeout=timeout)


def fetch_waves_at(latitude: float, longitude: float, timeout: float = 10.0) -> dict:
    """Return the live wave readout for any ocean point, or a fallback."""
    try:
        response = httpx.get(
            MARINE_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "wave_height",
                "timezone": "UTC",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        current = response.json()["current"]
        return {
            "source": "open-meteo",
            "live": True,
            "wave_height_m": round(float(current["wave_height"]), 2),
            "observed_at": current["time"],
        }
    except Exception:
        return {
            "source": "synthetic-fallback",
            "live": False,
            "wave_height_m": FALLBACK_WAVE_HEIGHT_M,
            "observed_at": None,
        }
