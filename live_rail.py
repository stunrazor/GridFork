"""Phase 2 rail layer: live Dutch rail disruptions from the NS API.

A free NS key is required: register at https://apiportal.ns.nl and set
NS_API_KEY (sent as the Ocp-Apim-Subscription-Key header, never logged or
returned). Without it, ``fetch_network_disruptions`` reports
``setup-required`` and performs no network call.
"""

import os

import httpx

DISRUPTIONS_URL = "https://gateway.apiportal.ns.nl/disruptions/v3"
SETUP_DETAIL = (
    "Free NS key needed: set NS_API_KEY from https://apiportal.ns.nl. "
    "The rail leg stays synthetic until then."
)


def fetch_network_disruptions(timeout: float = 10.0) -> dict:
    """Return live active-disruption counts, setup-required, or a fallback."""
    api_key = (os.environ.get("NS_API_KEY") or "").strip()
    if not api_key:
        return {
            "source": "setup-required",
            "live": False,
            "active_count": None,
            "rotterdam_count": None,
            "observed_at": None,
            "detail": SETUP_DETAIL,
        }
    try:
        response = httpx.get(
            DISRUPTIONS_URL,
            params={"isActive": "true"},
            headers={"Ocp-Apim-Subscription-Key": api_key},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            payload = payload.get("disruptions", [])
        if not isinstance(payload, list):
            raise ValueError("unexpected disruptions shape")
        titles = [str(item.get("title", "")) for item in payload]
        return {
            "source": "ns-disruptions",
            "live": True,
            "active_count": len(payload),
            "rotterdam_count": sum("rotterdam" in t.lower() for t in titles),
            # Per-disruption times exist; no global timestamp is returned.
            "observed_at": None,
        }
    except Exception:
        return {
            "source": "synthetic-fallback",
            "live": False,
            "active_count": None,
            "rotterdam_count": None,
            "observed_at": None,
        }
