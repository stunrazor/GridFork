"""Phase 2 rail layer: live disruptions from NS, Deutsche Bahn, or Entur.

Primary: a free NS key from https://apiportal.ns.nl, set as NS_API_KEY
(sent as the Ocp-Apim-Subscription-Key header, never logged or returned).
Second: free DB Timetables credentials from
https://developer.deutschebahn.com, set as DB_CLIENT_ID and DB_API_KEY.
Last: Norway's Entur JourneyPlanner, keyless (identifies as
``stunrazor-gridfork`` per its client-name policy). ``fetch_rail_disruptions``
tries them in that order and reports ``setup-required`` only when none
is reachable without credentials — in practice the Entur leg means rail
is live-capable out of the box.
"""

import os
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx

DISRUPTIONS_URL = "https://gateway.apiportal.ns.nl/disruptions/v3"
ENTUR_URL = "https://api.entur.io/journey-planner/v3/graphql"
ENTUR_CLIENT_NAME = "stunrazor-gridfork"
ENTUR_OSLO_S = "NSR:StopPlace:59872"
ENTUR_QUERY = """{
  stopPlace(id: "NSR:StopPlace:59872") {
    estimatedCalls(numberOfDepartures: 20, timeRange: 7200) {
      aimedDepartureTime
      expectedDepartureTime
      cancellation
    }
  }
}"""
ENTUR_DELAY_MINUTES = 10
DB_FCHG_URL = (
    "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1"
    "/fchg/{eva}"
)
# Largest corridor station inside the DB network.
DB_STATION_EVA = "8002549"  # Hamburg Hbf
# A stop counts as disrupted on cancellation or a 10+ minute delay;
# platform-only changes are routine and ignored.
DB_DELAY_MINUTES = 10
NS_SETUP_DETAIL = (
    "Free NS key needed: set NS_API_KEY from https://apiportal.ns.nl. "
    "The rail leg stays synthetic until then."
)
DB_SETUP_DETAIL = (
    "Free DB Timetables credentials needed: set DB_CLIENT_ID and "
    "DB_API_KEY from https://developer.deutschebahn.com."
)


def fetch_network_disruptions(timeout: float = 10.0) -> dict:
    """Return live NS active-disruption counts, setup-required, or fallback."""
    api_key = (os.environ.get("NS_API_KEY") or "").strip()
    if not api_key:
        return {
            "source": "setup-required",
            "live": False,
            "active_count": None,
            "rotterdam_count": None,
            "observed_at": None,
            "detail": NS_SETUP_DETAIL,
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


def _event_delay_minutes(event) -> int | None:
    """Planned-to-actual delay in minutes; None when unparseable."""
    try:
        planned = datetime.strptime(event.get("pt"), "%y%m%d%H%M")
        changed = datetime.strptime(event.get("ct"), "%y%m%d%H%M")
    except (TypeError, ValueError):
        return None
    return round((changed - planned).total_seconds() / 60)


def _stop_disruption(stop) -> tuple[bool, bool]:
    """Assess one fchg stop as (disrupted, cancelled)."""
    disrupted = False
    cancelled = False
    for event in (*stop.findall("ar"), *stop.findall("dp")):
        if event.get("cs") == "c":
            return True, True
        delay = _event_delay_minutes(event)
        if delay is not None and delay >= DB_DELAY_MINUTES:
            disrupted = True
    return disrupted, cancelled


def fetch_db_disruptions(timeout: float = 10.0) -> dict:
    """Return live DB disruption counts, setup-required, or a fallback."""
    client_id = (os.environ.get("DB_CLIENT_ID") or "").strip()
    api_key = (os.environ.get("DB_API_KEY") or "").strip()
    if not client_id or not api_key:
        return {
            "source": "setup-required",
            "live": False,
            "active_count": None,
            "severe_count": None,
            "observed_at": None,
            "detail": DB_SETUP_DETAIL,
        }
    try:
        response = httpx.get(
            DB_FCHG_URL.format(eva=DB_STATION_EVA),
            headers={"DB-Client-Id": client_id, "DB-Api-Key": api_key},
            timeout=timeout,
        )
        response.raise_for_status()
        stops = ET.fromstring(response.text).findall("s")
        active = 0
        severe = 0
        for stop in stops:
            disrupted, cancelled = _stop_disruption(stop)
            active += disrupted
            severe += cancelled
        return {
            "source": "db-timetables",
            "live": True,
            "active_count": active,
            "severe_count": severe,
            "observed_at": None,
        }
    except Exception:
        return {
            "source": "synthetic-fallback",
            "live": False,
            "active_count": None,
            "severe_count": None,
            "observed_at": None,
        }


def fetch_entur_disruptions(
    timeout: float = 10.0, stop_id: str = ENTUR_OSLO_S
) -> dict:
    """Return live disruption counts for a stop, keyless, or a fallback.

    Counts cancellations plus 10+ minute delays among the next 20
    departures; routine small delays are ignored. Defaults to Oslo S;
    worldwide corridors pass their own stop id.
    """
    try:
        response = httpx.post(
            ENTUR_URL,
            json={"query": ENTUR_QUERY.replace(ENTUR_OSLO_S, stop_id)},
            headers={"ET-Client-Name": ENTUR_CLIENT_NAME},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise ValueError("entur query errors")
        calls = payload["data"]["stopPlace"]["estimatedCalls"]
        active = 0
        severe = 0
        for call in calls:
            if call.get("cancellation"):
                active += 1
                severe += 1
                continue
            try:
                aimed = datetime.fromisoformat(call["aimedDepartureTime"])
                expected = datetime.fromisoformat(call["expectedDepartureTime"])
            except (TypeError, ValueError):
                continue
            if (expected - aimed).total_seconds() / 60 >= ENTUR_DELAY_MINUTES:
                active += 1
        return {
            "source": "entur",
            "live": True,
            "active_count": active,
            "severe_count": severe,
            "observed_at": None,
        }
    except Exception:
        return {
            "source": "synthetic-fallback",
            "live": False,
            "active_count": None,
            "severe_count": None,
            "observed_at": None,
        }


def fetch_rail_disruptions(
    timeout: float = 10.0, entur_stop: str = ENTUR_OSLO_S
) -> dict:
    """Return live rail disruptions: NS, else DB, else keyless Entur.

    The readout shape is unified: ``active_count`` counts disruptions and
    ``severe_count`` counts the severe subset (Rotterdam mentions for NS,
    cancellations for DB and Entur); ``source`` says which provider
    answered. ``entur_stop`` carries the worldwide stop id; NS/DB keep
    their country networks.
    """
    first_failure = None
    if (os.environ.get("NS_API_KEY") or "").strip():
        ns = fetch_network_disruptions(timeout=timeout)
        if ns["live"]:
            return {
                "source": ns["source"],
                "live": True,
                "active_count": ns["active_count"],
                "severe_count": ns["rotterdam_count"],
                "observed_at": ns["observed_at"],
            }
        first_failure = {
            "source": ns["source"],
            "live": False,
            "active_count": None,
            "severe_count": None,
            "observed_at": None,
        }
    if (os.environ.get("DB_CLIENT_ID") or "").strip() and (
        os.environ.get("DB_API_KEY") or ""
    ).strip():
        db = fetch_db_disruptions(timeout=timeout)
        if db["live"]:
            return db
        if first_failure is None:
            first_failure = db
    entur = fetch_entur_disruptions(timeout=timeout, stop_id=entur_stop)
    if entur["live"]:
        return entur
    return first_failure if first_failure is not None else entur
