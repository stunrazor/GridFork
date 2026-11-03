"""Phase 2 vessel layer: live ship traffic from AISStream.io.

A free AISStream key is required: sign in with GitHub at
https://aisstream.io, create an API key, and set AISSTREAM_API_KEY.
Without it, ``fetch_vessel_traffic`` reports ``setup-required`` and
performs no network call. The feed is a WebSocket stream; each call
subscribes with bounding boxes, collects position reports for a short
window, and counts unique vessels (MMSI) per box. Counts are measured
context for the sea leg; no validated congestion-to-delay rule exists,
so they never move the delay number.
"""

import json
import os
import threading
import time
from datetime import datetime, timezone

from websockets.sync.client import connect as _ws_connect

STREAM_URL = "wss://stream.aisstream.io/v0/stream"
# Default watch boxes: the world's busiest cargo/tanker chokepoints,
# widened to ~2 degrees. AISStream's community receivers are sparse, so
# a tight box samples almost nothing even in a busy strait.
HORMUZ_BOX = {"lamin": 25.4, "lomin": 55.3, "lamax": 27.4, "lomax": 57.3}
DOVER_BOX = {"lamin": 50.0, "lomin": 0.4, "lamax": 52.0, "lomax": 2.4}
SUEZ_BOX = {"lamin": 29.7, "lomin": 31.4, "lamax": 31.7, "lomax": 33.5}
DEFAULT_BOXES = (
    ("hormuz", HORMUZ_BOX),
    ("dover", DOVER_BOX),
    ("suez", SUEZ_BOX),
)
SETUP_DETAIL = (
    "Free AISStream key needed: sign in with GitHub at "
    "https://aisstream.io, create an API key, and set AISSTREAM_API_KEY. "
    "Vessel counts stay unavailable until then."
)
# AISStream throttles rapid reconnects (HTTP 429 on the handshake), and
# every page view would otherwise open a fresh stream, so successful
# readouts are reused briefly. Failures are never cached: recovery is
# immediate on the next call. ``observed_at`` always says when the
# stream was actually read.
_VESSEL_CACHE: dict = {}
_VESSEL_CACHE_TTL = 120.0
_VESSEL_CACHE_LOCK = threading.Lock()


def clear_vessel_cache() -> None:
    """Drop cached vessel readouts (tests and key rotation)."""
    with _VESSEL_CACHE_LOCK:
        _VESSEL_CACHE.clear()


def _connect(url: str, timeout: float):
    """Open a compressed stream connection (wrapper for tests).

    Compression is required, not optional: AISStream bandwidth-limits
    uncompressed connections and drops most of their messages.
    """
    return _ws_connect(url, open_timeout=timeout, compression="deflate")


def point_box(lat: float, lon: float, half: float = 0.5) -> dict:
    """Small AIS box around a point, shaped like the OpenSky boxes."""
    return {
        "lamin": round(lat - half, 2),
        "lomin": round(lon - half, 2),
        "lamax": round(lat + half, 2),
        "lomax": round(lon + half, 2),
    }


def _to_stream_boxes(boxes) -> list:
    """Convert lamin/lomin/lamax/lomax dicts to AISStream corners."""
    return [
        [[box["lamin"], box["lomin"]], [box["lamax"], box["lomax"]]]
        for _, box in boxes
    ]


def _in_box(lat: float, lon: float, box: dict) -> bool:
    """True when a position falls inside a lamin/lomin/lamax/lomax box."""
    return (
        box["lamin"] <= lat <= box["lamax"]
        and box["lomin"] <= lon <= box["lomax"]
    )


def _parse_report(raw):
    """Extract (mmsi, lat, lon, stamp) from a stream envelope.

    Returns None for anything malformed or not a position report; the
    stream carries other message types and service frames.
    """
    try:
        envelope = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(envelope, dict):
        return None
    if envelope.get("MessageType") != "PositionReport":
        return None
    meta = envelope.get("MetaData") or {}
    message = envelope.get("Message") or {}
    report = message.get("PositionReport") or {}
    # Position placement varies: the docs show capitalized MetaData,
    # live frames carry the full body plus lowercase MetaData. Accept
    # capitalized MetaData, then the body, then lowercase MetaData.
    try:
        lat = float(meta.get("Latitude", report.get("Latitude", meta.get("latitude"))))
        lon = float(meta.get("Longitude", report.get("Longitude", meta.get("longitude"))))
    except (TypeError, ValueError):
        return None
    mmsi = meta.get("MMSI")
    if mmsi is None:
        return None
    return mmsi, lat, lon, meta.get("time_utc")


def _failure_detail(exc: Exception) -> str:
    """One-line failure class for a fallback readout; secret-free."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is None:
        # Some handshake failures carry the status directly.
        status = getattr(exc, "status_code", None)
    if status is not None:
        return f"{type(exc).__name__} {status}"
    return type(exc).__name__


def fetch_vessel_traffic(
    timeout: float = 10.0,
    boxes: tuple = DEFAULT_BOXES,
    duration: float = 5.0,
) -> dict:
    """Return live unique-vessel counts per box, or a labeled fallback.

    ``boxes`` is ``(tag, box)`` pairs; counts land under
    ``vessels_<tag>``. Defaults watch Hormuz, Dover, and Suez;
    corridors pass their own sea-point box. ``duration`` caps the
    collection window (never beyond ``timeout``); ``window_seconds``
    reports how long the stream was actually read.
    """
    blank = {f"vessels_{tag}": None for tag, _ in boxes}
    api_key = (os.environ.get("AISSTREAM_API_KEY") or "").strip()
    if not api_key:
        return {
            "source": "setup-required",
            "live": False,
            **blank,
            "vessels_total": None,
            "observed_at": None,
            "detail": SETUP_DETAIL,
        }
    cache_key = (
        tuple((tag, tuple(sorted(box.items()))) for tag, box in boxes),
        duration,
    )
    with _VESSEL_CACHE_LOCK:
        hit = _VESSEL_CACHE.get(cache_key)
        if hit is not None and time.monotonic() < hit[0]:
            return dict(hit[1])
    window = max(0.5, min(duration, timeout))
    seen: dict = {tag: set() for tag, _ in boxes}
    stamp = None
    start = time.monotonic()
    try:
        with _connect(STREAM_URL, timeout) as ws:
            ws.send(
                json.dumps(
                    {
                        "APIKey": api_key,
                        "BoundingBoxes": _to_stream_boxes(boxes),
                        "FilterMessageTypes": ["PositionReport"],
                    }
                )
            )
            while time.monotonic() - start < window:
                try:
                    raw = ws.recv(
                        timeout=max(0.1, window - (time.monotonic() - start))
                    )
                except TimeoutError:
                    break
                parsed = _parse_report(raw)
                if parsed is None:
                    continue
                mmsi, lat, lon, reported = parsed
                for tag, box in boxes:
                    if _in_box(lat, lon, box):
                        seen[tag].add(mmsi)
                        break
                if reported:
                    stamp = reported
            counts = {f"vessels_{tag}": len(seen[tag]) for tag, _ in boxes}
            readout = {
                "source": "aisstream",
                "live": True,
                **counts,
                "vessels_total": sum(counts.values()),
                "window_seconds": round(time.monotonic() - start, 1),
                "observed_at": stamp
                or datetime.now(tz=timezone.utc).isoformat(),
            }
        with _VESSEL_CACHE_LOCK:
            _VESSEL_CACHE[cache_key] = (
                time.monotonic() + _VESSEL_CACHE_TTL,
                readout,
            )
        return dict(readout)
    except Exception as exc:
        return {
            "source": "estimated-fallback",
            "live": False,
            **blank,
            "vessels_total": None,
            "observed_at": None,
            "detail": _failure_detail(exc),
        }
