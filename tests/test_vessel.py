"""Tests for the vessel/AIS live layer (fully mocked, no network).

The vessel layer counts unique ships (MMSI) per bounding box over a short
AISStream window. Setup-required and fallback paths mirror the air layer:
no key means no network call, and any stream failure stays labeled.
"""

import json

import websocket

import geo
import live_air
import live_marine
import live_rail
import live_road
import live_vessel
import live_weather
import snapshot as snapshot_mod
from landing_page import render_landing
from main import vessel_traffic
from orchestrator import apply_phase2_layers
from spark_client import build_ask_context

STAMP = "2026-11-03T00:00:00+00:00"
HORMUZ = ("hormuz", {"lamin": 25.8, "lomin": 55.8, "lamax": 27.0, "lomax": 56.8})
SUEZ = ("suez", {"lamin": 29.8, "lomin": 32.2, "lamax": 31.6, "lomax": 32.7})


def _report(mmsi, lat, lon, stamp=STAMP):
    # Real AISStream shape: normalized position in MetaData.
    return json.dumps(
        {
            "MessageType": "PositionReport",
            "Message": {"PositionReport": {"MessageID": 1, "UserID": mmsi}},
            "MetaData": {
                "MMSI": mmsi,
                "ShipName": "EXAMPLE VESSEL",
                "Latitude": lat,
                "Longitude": lon,
                "time_utc": stamp,
            },
        }
    )


def _body_report(mmsi, lat, lon):
    # Older/alternate shape: position only in the message body.
    return json.dumps(
        {
            "MessageType": "PositionReport",
            "Message": {"PositionReport": {"Latitude": lat, "Longitude": lon}},
            "MetaData": {"MMSI": mmsi},
        }
    )


class _FakeWS:
    """Canned stream: yields frames, then ends the window like a timeout."""

    def __init__(self, frames):
        self.frames = list(frames)
        self.sent = []
        self.closed = False

    def send(self, payload):
        self.sent.append(payload)

    def settimeout(self, seconds):
        pass

    def recv(self):
        if self.frames:
            return self.frames.pop(0)
        raise websocket.WebSocketTimeoutException("window over")

    def close(self):
        self.closed = True


def _patch_all(monkeypatch, vessels_total=42):
    """Rig every live client a snapshot touches, vessel included."""
    monkeypatch.setattr(
        live_marine,
        "fetch_waves_at",
        lambda lat, lon, timeout=10.0: {
            "source": "open-meteo",
            "live": True,
            "wave_height_m": 0.4,
            "observed_at": "2026-11-02T00:00",
        },
    )
    monkeypatch.setattr(
        live_weather,
        "fetch_wind_at",
        lambda lat, lon, timeout=10.0: {
            "source": "open-meteo",
            "live": True,
            "wind_kph": 20.0,
            "observed_at": "2026-11-02T00:00",
        },
    )
    monkeypatch.setattr(
        live_air,
        "fetch_air_traffic",
        lambda timeout=10.0, boxes=None, points=None: {
            "source": "adsb-lol",
            "live": True,
            "airborne_origin": 8,
            "airborne_dest": 4,
            "observed_at": "2026-11-02T00:00+00:00",
        },
    )
    monkeypatch.setattr(
        live_road,
        "fetch_corridor_congestion",
        lambda timeout=10.0, points=(), origin=(), dest=(): {
            "source": "tomtom",
            "live": True,
            "worst_ratio": 1.0,
            "points": [{"label": "p", "ratio": 1.0}],
            "incidents": None,
            "route": None,
            "observed_at": None,
        },
    )
    monkeypatch.setattr(
        live_rail,
        "fetch_entur_disruptions",
        lambda timeout=10.0, stop_id="x": {
            "source": "entur",
            "live": True,
            "active_count": 0,
            "severe_count": 0,
            "observed_at": None,
        },
    )
    monkeypatch.setattr(
        geo, "nearest_entur_stop", lambda lat, lon, timeout=10.0: ("stop", "Oslo S")
    )
    monkeypatch.setattr(
        live_vessel,
        "fetch_vessel_traffic",
        lambda timeout=10.0, boxes=(), duration=5.0: {
            "source": "aisstream",
            "live": True,
            "vessels_sea": vessels_total,
            "vessels_total": vessels_total,
            "observed_at": STAMP,
        },
    )


def test_vessel_setup_required_without_key(monkeypatch):
    monkeypatch.delenv("AISSTREAM_API_KEY", raising=False)

    def explode(*args, **kwargs):
        raise AssertionError("setup-required must not touch the network")

    monkeypatch.setattr(live_vessel, "create_connection", explode)
    readout = live_vessel.fetch_vessel_traffic()
    assert readout["source"] == "setup-required"
    assert readout["live"] is False
    assert readout["vessels_hormuz"] is None
    assert readout["vessels_total"] is None
    assert readout["observed_at"] is None
    assert "AISSTREAM_API_KEY" in readout["detail"]


def test_vessel_counts_unique_mmsi_per_box(monkeypatch):
    monkeypatch.setenv("AISSTREAM_API_KEY", "unit-ais-key")
    fake = _FakeWS(
        [
            _report(111, 26.5, 56.2),
            _report(222, 26.6, 56.3),
            _report(111, 26.5, 56.2),  # same ship twice: counted once
            _report(333, 31.0, 32.4),
            _report(444, 0.0, 0.0),  # outside every box: ignored
        ]
    )
    monkeypatch.setattr(live_vessel, "create_connection", lambda *a, **k: fake)
    readout = live_vessel.fetch_vessel_traffic(
        boxes=(HORMUZ, SUEZ), duration=5.0
    )
    assert readout["source"] == "aisstream"
    assert readout["live"] is True
    assert readout["vessels_hormuz"] == 2
    assert readout["vessels_suez"] == 1
    assert readout["vessels_total"] == 3
    assert readout["observed_at"] == STAMP
    assert fake.closed is True
    subscription = json.loads(fake.sent[0])
    assert subscription["APIKey"] == "unit-ais-key"
    assert len(subscription["BoundingBoxes"]) == 2
    assert subscription["FilterMessageTypes"] == ["PositionReport"]


def test_vessel_skips_malformed_frames(monkeypatch):
    monkeypatch.setenv("AISSTREAM_API_KEY", "unit-ais-key")
    fake = _FakeWS(
        [
            "not json",
            json.dumps({"MessageType": "ShipStaticData"}),
            json.dumps({"MessageType": "PositionReport", "Message": {}}),
            _report(555, 26.5, 56.2),
        ]
    )
    monkeypatch.setattr(live_vessel, "create_connection", lambda *a, **k: fake)
    readout = live_vessel.fetch_vessel_traffic(boxes=(HORMUZ,))
    assert readout["live"] is True
    assert readout["vessels_hormuz"] == 1
    assert readout["vessels_total"] == 1


def test_vessel_falls_back_to_message_body_position(monkeypatch):
    monkeypatch.setenv("AISSTREAM_API_KEY", "unit-ais-key")
    fake = _FakeWS([_body_report(777, 26.5, 56.2)])
    monkeypatch.setattr(live_vessel, "create_connection", lambda *a, **k: fake)
    readout = live_vessel.fetch_vessel_traffic(boxes=(HORMUZ,))
    assert readout["live"] is True
    assert readout["vessels_hormuz"] == 1


def test_vessel_handshake_status_stays_in_detail(monkeypatch):
    monkeypatch.setenv("AISSTREAM_API_KEY", "unit-ais-key")

    def refused(*args, **kwargs):
        raise websocket.WebSocketBadStatusException("handshake %s", 401)

    monkeypatch.setattr(live_vessel, "create_connection", refused)
    readout = live_vessel.fetch_vessel_traffic(boxes=(HORMUZ,))
    assert readout["source"] == "estimated-fallback"
    assert readout["detail"] == "WebSocketBadStatusException 401"


def test_vessel_failure_falls_back_labeled(monkeypatch):
    monkeypatch.setenv("AISSTREAM_API_KEY", "unit-ais-key")

    def down(*args, **kwargs):
        raise ConnectionError("stream unreachable")

    monkeypatch.setattr(live_vessel, "create_connection", down)
    readout = live_vessel.fetch_vessel_traffic(boxes=(HORMUZ,))
    assert readout["source"] == "estimated-fallback"
    assert readout["live"] is False
    assert readout["vessels_hormuz"] is None
    assert readout["detail"] == "ConnectionError"


def test_snapshot_sea_carries_vessel_count(monkeypatch):
    _patch_all(monkeypatch, vessels_total=42)
    snap = snapshot_mod.build_snapshot(
        {"name": "Singapore", "lat": 1.26, "lon": 103.82},
        {"name": "Rotterdam", "lat": 51.95, "lon": 4.14},
        "Singapore → Rotterdam",
    )
    assert snap["vessel"]["live"] is True
    assert snap["vessel"]["vessels_total"] == 42
    assert snap["legs"]["sea"]["vessels_nearby"] == 42
    assert snap["provenance"]["sea"]["vessels_nearby"] == "measured"


def test_snapshot_short_hop_skips_vessel_stream(monkeypatch):
    _patch_all(monkeypatch)

    def explode(*args, **kwargs):
        raise AssertionError("short hop must not open the vessel stream")

    monkeypatch.setattr(live_vessel, "fetch_vessel_traffic", explode)
    snap = snapshot_mod.build_snapshot(
        {"name": "Baliuag", "lat": 14.95, "lon": 120.90},
        {"name": "Malolos", "lat": 15.05, "lon": 120.95},
        "Baliuag → Malolos",
    )
    assert snap["vessel"]["source"] == "not-applicable"
    assert snap["legs"]["sea"]["applicable"] is False


def test_apply_vessel_to_demo_sea_slice():
    scenario = {"modes": {"sea": {}, "air": {}, "road": {}, "rail": {}}}
    provenance = {"sea": {}, "air": {}, "road": {}, "rail": {}}
    dead = {"live": False}
    vessel = {"live": True, "source": "aisstream", "vessels_total": 17}
    apply_phase2_layers(scenario, provenance, dead, dead, dead, vessel)
    assert scenario["modes"]["sea"]["vessels_nearby"] == 17
    assert provenance["sea"]["vessels_nearby"] == "measured"
    assert "delay_hours" not in scenario["modes"]["sea"]


def test_apply_without_vessel_leaves_demo_sea_untouched():
    scenario = {"modes": {"sea": {}, "air": {}, "road": {}, "rail": {}}}
    provenance = {"sea": {}, "air": {}, "road": {}, "rail": {}}
    dead = {"live": False}
    apply_phase2_layers(scenario, provenance, dead, dead, dead)
    assert "vessels_nearby" not in scenario["modes"]["sea"]
    assert "vessels_nearby" not in provenance["sea"]


def _live_block(vessel):
    return {
        "provenance": {},
        "marine": {},
        "wind": {},
        "air": {},
        "road": {},
        "rail": {},
        "vessel": vessel,
    }


def test_ask_grounding_includes_live_vessels():
    findings = [
        {
            "mode": "sea",
            "status": "available",
            "delay_hours": 2,
            "cost_usd": 1800,
            "on_time_probability": 0.9,
            "summary": "Calm seas.",
        }
    ]
    ranked = [
        {
            "rank": 1,
            "option_id": "sea-wait",
            "title": "Wait",
            "score": 0.7,
            "cost_usd": 1800,
            "time_saved_hours": 1,
            "on_time_probability": 0.9,
            "confidence": 0.6,
        }
    ]
    live = _live_block({"live": True, "source": "aisstream", "vessels_total": 42})
    text = "\n".join(build_ask_context(findings, ranked, live))
    assert "vessels: 42 tracked near the sea leg [aisstream]." in text
    quiet = "\n".join(build_ask_context(findings, ranked, _live_block(None)))
    assert "vessels:" not in quiet


def test_vessels_endpoint_returns_readout(monkeypatch):
    readout = {
        "source": "aisstream",
        "live": True,
        "vessels_hormuz": 30,
        "vessels_dover": 12,
        "vessels_suez": 8,
        "vessels_total": 50,
        "observed_at": STAMP,
    }
    monkeypatch.setattr(
        live_vessel, "fetch_vessel_traffic", lambda **kwargs: readout
    )
    assert vessel_traffic() == readout


def test_homepage_labels_each_watched_sea():
    html = render_landing()
    assert '"/vessels"' in html
    for label in ("Strait of Hormuz", "English Channel", "Suez Canal"):
        assert label in html
    assert "(North Sea)" in html
    assert "Sea traffic" in html
    script = html.split("<script>", 1)[1]
    assert "innerHTML" not in script
