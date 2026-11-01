"""Phase 2 air layer: live corridor traffic from the OpenSky Network.

A free OpenSky account is required: register at https://opensky-network.org,
create an OAuth2 client, and set OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET.
Without both, ``fetch_corridor_traffic`` reports ``setup-required`` and
performs no network call. OpenSky accepts only the OAuth2 client-credentials
flow; username/password Basic auth was retired.
"""

import os
from datetime import datetime, timezone

import httpx

TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network"
    "/protocol/openid-connect/token"
)
STATES_URL = "https://opensky-network.org/api/states/all"
# Keyless backup: community ADS-B aggregator, no account. Used when OpenSky
# has no credentials or is unreachable (e.g. filtered egress networks).
ADSB_URL = "https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/{nm}"
ADSB_AMS = (52.31, 4.76)
ADSB_OSL = (60.19, 11.10)
ADSB_RADIUS_NM = 25
# Small boxes around each end of the AMS-OSL air bridge, well under the
# lowest-cost API tier each.
AMS_BOX = {"lamin": 51.8, "lomin": 4.2, "lamax": 52.6, "lomax": 5.4}
OSL_BOX = {"lamin": 59.8, "lomin": 10.6, "lamax": 60.6, "lomax": 11.6}
SETUP_DETAIL = (
    "Free OpenSky account needed: set OPENSKY_CLIENT_ID and "
    "OPENSKY_CLIENT_SECRET from an OAuth2 client at "
    "https://opensky-network.org. The air leg stays synthetic until then."
)


def _count_airborne(states) -> int:
    """Count explicitly airborne contacts; unknown or short rows are skipped."""
    airborne = 0
    for state in states or []:
        if len(state) > 8 and state[8] is False:
            airborne += 1
    return airborne


def fetch_corridor_traffic(timeout: float = 10.0) -> dict:
    """Return live AMS/OSL traffic counts, setup-required, or a fallback."""
    client_id = (os.environ.get("OPENSKY_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("OPENSKY_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        return {
            "source": "setup-required",
            "live": False,
            "airborne_ams": None,
            "airborne_osl": None,
            "observed_at": None,
            "detail": SETUP_DETAIL,
        }
    try:
        token = httpx.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=timeout,
        )
        token.raise_for_status()
        headers = {"Authorization": f"Bearer {token.json()['access_token']}"}
        counts = {}
        observed = None
        for tag, box in (("ams", AMS_BOX), ("osl", OSL_BOX)):
            response = httpx.get(
                STATES_URL, params=dict(box), headers=headers, timeout=timeout
            )
            response.raise_for_status()
            payload = response.json()
            counts[tag] = _count_airborne(payload.get("states"))
            observed = payload["time"]
        return {
            "source": "opensky",
            "live": True,
            "airborne_ams": counts["ams"],
            "airborne_osl": counts["osl"],
            "observed_at": datetime.fromtimestamp(observed, tz=timezone.utc).isoformat(),
        }
    except Exception as exc:
        return {
            "source": "synthetic-fallback",
            "live": False,
            "airborne_ams": None,
            "airborne_osl": None,
            "observed_at": None,
            # Failure class only (never URLs, headers, or bodies) so a
            # production fallback stays diagnosable without leaking secrets.
            "detail": _failure_detail(exc),
        }


def _failure_detail(exc: Exception) -> str:
    """One-line failure class for a fallback readout; secret-free."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is not None:
        return f"{type(exc).__name__} {status}"
    return type(exc).__name__


def _count_adsb_airborne(aircraft: list) -> int:
    """Count contacts reporting positive barometric altitude.

    Ground-level and altitude-unknown contacts are excluded, matching the
    OpenSky airborne-only semantics as closely as the schema allows.
    """
    airborne = 0
    for contact in aircraft or []:
        altitude = contact.get("alt_baro")
        if isinstance(altitude, (int, float)) and altitude > 0:
            airborne += 1
    return airborne


def fetch_adsb_traffic(timeout: float = 10.0) -> dict:
    """Return live AMS/OSL traffic counts from adsb.lol, or a fallback."""
    try:
        counts = {}
        observed = None
        for tag, (lat, lon) in (("ams", ADSB_AMS), ("osl", ADSB_OSL)):
            response = httpx.get(
                ADSB_URL.format(lat=lat, lon=lon, nm=ADSB_RADIUS_NM),
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            counts[tag] = _count_adsb_airborne(payload.get("ac"))
            observed = payload.get("now", observed)
        try:
            observed_at = datetime.fromtimestamp(observed, tz=timezone.utc).isoformat()
        except (TypeError, ValueError):
            observed_at = None
        return {
            "source": "adsb-lol",
            "live": True,
            "airborne_ams": counts["ams"],
            "airborne_osl": counts["osl"],
            "observed_at": observed_at,
        }
    except Exception as exc:
        return {
            "source": "synthetic-fallback",
            "live": False,
            "airborne_ams": None,
            "airborne_osl": None,
            "observed_at": None,
            "detail": _failure_detail(exc),
        }


def fetch_air_traffic(timeout: float = 10.0) -> dict:
    """Return live air traffic: OpenSky, else keyless adsb.lol.

    OpenSky is tried when credentials are set; adsb.lol whenever OpenSky
    is unconfigured or fails. ``source`` says which provider answered.
    """
    first_failure = None
    if (os.environ.get("OPENSKY_CLIENT_ID") or "").strip() and (
        os.environ.get("OPENSKY_CLIENT_SECRET") or ""
    ).strip():
        opensky = fetch_corridor_traffic(timeout=timeout)
        if opensky["live"]:
            return opensky
        if opensky["source"] != "setup-required":
            first_failure = opensky
    adsb = fetch_adsb_traffic(timeout=timeout)
    if adsb["live"]:
        return adsb
    return first_failure if first_failure is not None else adsb
