"""One live data layer: current Rotterdam wind from Open-Meteo.

Open-Meteo needs no API key: ``GET /v1/forecast`` with latitude/longitude
returns JSON with ``current.wind_speed_10m`` in m/s. Any failure (network
error, bad response) falls back to a clearly labeled synthetic value so the
demo keeps working offline.
"""

import httpx

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
LATITUDE = 51.95
LONGITUDE = 4.14
# Matches the synthetic storm slice; used only when clearly labeled fallback.
FALLBACK_WIND_KPH = 110.0


def fetch_rotterdam_wind(timeout: float = 10.0) -> dict:
    """Return the live wind readout, or a labeled synthetic fallback."""
    return fetch_wind_at(LATITUDE, LONGITUDE, timeout=timeout)


def fetch_wind_at(latitude: float, longitude: float, timeout: float = 10.0) -> dict:
    """Return the live wind readout for any point, or a fallback."""
    try:
        response = httpx.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "wind_speed_10m",
                "wind_speed_unit": "ms",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        current = response.json()["current"]
        kph = round(float(current["wind_speed_10m"]) * 3.6, 1)
        return {
            "source": "open-meteo",
            "live": True,
            "wind_kph": kph,
            "observed_at": current["time"],
        }
    except Exception:
        return {
            "source": "synthetic-fallback",
            "live": False,
            "wind_kph": FALLBACK_WIND_KPH,
            "observed_at": None,
        }
