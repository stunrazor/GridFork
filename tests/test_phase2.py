"""Tests for the Phase 2 live layers (fully mocked, no network).

Phase 2 adds air (OpenSky), road (TomTom), and rail (NS disruptions) layers
to the live snapshot. Every test is hermetic: credentials come from
monkeypatched env vars, and setup-required tests prove no network call is
attempted by rigging httpx to explode.
"""

import os
from datetime import datetime, timezone

import httpx

import live_air
import live_marine
import live_rail
import live_road
import live_weather
from grid_page import render_grid_page
from main import north_sea_storm_live
from orchestrator import run_demo, run_live_snapshot

OPEN_SKY_TIME = 1793474000


def _clear_phase2_env(monkeypatch):
    for var in (
        "OPENSKY_CLIENT_ID",
        "OPENSKY_CLIENT_SECRET",
        "TOMTOM_API_KEY",
        "NS_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


def _set_phase2_env(monkeypatch):
    monkeypatch.setenv("OPENSKY_CLIENT_ID", "unit-opensky-id")
    monkeypatch.setenv("OPENSKY_CLIENT_SECRET", "unit-opensky-secret")
    monkeypatch.setenv("TOMTOM_API_KEY", "unit-tomtom-key")
    monkeypatch.setenv("NS_API_KEY", "unit-ns-key")


def _no_network(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("setup-required must not touch the network")

    monkeypatch.setattr(httpx, "get", explode)
    monkeypatch.setattr(httpx, "post", explode)


def _state(icao, on_ground=False):
    # OpenSky state vector: index 5 lon, 6 lat, 8 on_ground.
    return [
        icao,
        "CALLSIGN",
        "Country",
        OPEN_SKY_TIME,
        OPEN_SKY_TIME,
        4.7,
        52.3,
        10000.0,
        on_ground,
        250.0,
    ]


def _states_response(states):
    return httpx.Response(
        200,
        json={"time": OPEN_SKY_TIME, "states": states},
        request=httpx.Request("GET", live_air.STATES_URL),
    )


def _ok_marine(wave_height=0.4):
    return httpx.Response(
        200,
        json={"current": {"time": "2026-10-31T19:15", "wave_height": wave_height}},
        request=httpx.Request("GET", live_marine.MARINE_URL),
    )


def _ok_wind(kph=45.0):
    return httpx.Response(
        200,
        json={"current": {"time": "2026-10-31T19:15", "wind_speed_10m": kph / 3.6}},
        request=httpx.Request("GET", live_weather.FORECAST_URL),
    )


def _flow_response(current, free):
    return httpx.Response(
        200,
        json={"flowSegmentData": {"currentSpeed": current, "freeFlowSpeed": free}},
        request=httpx.Request("GET", live_road.FLOW_URL),
    )


def test_air_setup_required_without_credentials(monkeypatch):
    _clear_phase2_env(monkeypatch)
    _no_network(monkeypatch)
    result = live_air.fetch_corridor_traffic()
    assert result["source"] == "setup-required"
    assert result["live"] is False
    assert "OPENSKY_CLIENT_ID" in result["detail"]
    assert "OPENSKY_CLIENT_SECRET" in result["detail"]


def test_air_live_counts_airborne_per_airport(monkeypatch):
    _set_phase2_env(monkeypatch)
    captured = {}

    def fake_post(url, data=None, timeout=None):
        captured["token_url"] = url
        assert data["client_id"] == os.environ["OPENSKY_CLIENT_ID"]
        assert data["client_secret"] == os.environ["OPENSKY_CLIENT_SECRET"]
        return httpx.Response(
            200,
            json={"access_token": os.environ["OPENSKY_CLIENT_SECRET"] + "-token"},
            request=httpx.Request("POST", live_air.TOKEN_URL),
        )

    def fake_get(url, params=None, headers=None, timeout=None):
        assert headers["Authorization"] == (
            "Bearer " + os.environ["OPENSKY_CLIENT_SECRET"] + "-token"
        )
        if params["lamin"] < 55:
            return _states_response([_state(f"ams{i}") for i in range(12)])
        return _states_response([_state(f"osl{i}") for i in range(3)])

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", fake_get)
    result = live_air.fetch_corridor_traffic()
    assert result["source"] == "opensky"
    assert result["live"] is True
    assert result["airborne_ams"] == 12
    assert result["airborne_osl"] == 3
    assert result["observed_at"] == (
        datetime.fromtimestamp(OPEN_SKY_TIME, tz=timezone.utc).isoformat()
    )
    assert captured["token_url"] == live_air.TOKEN_URL


def test_air_ignores_on_ground_contacts(monkeypatch):
    _set_phase2_env(monkeypatch)
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, data=None, timeout=None: httpx.Response(
            200,
            json={"access_token": "airport-surface-sample"},
            request=httpx.Request("POST", live_air.TOKEN_URL),
        ),
    )
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: _states_response([_state("g1", True)])
    )
    result = live_air.fetch_corridor_traffic()
    assert result["live"] is True
    assert result["airborne_ams"] == 0
    assert result["airborne_osl"] == 0


def test_air_falls_back_labeled_when_call_fails(monkeypatch):
    _set_phase2_env(monkeypatch)

    def error_post(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "post", error_post)
    result = live_air.fetch_corridor_traffic()
    assert result["source"] == "synthetic-fallback"
    assert result["live"] is False


def test_road_setup_required_without_key(monkeypatch):
    _clear_phase2_env(monkeypatch)
    _no_network(monkeypatch)
    result = live_road.fetch_corridor_congestion()
    assert result["source"] == "setup-required"
    assert result["live"] is False
    assert "TOMTOM_API_KEY" in result["detail"]


def test_road_live_reports_worst_ratio(monkeypatch):
    _set_phase2_env(monkeypatch)
    captured = {}
    ratios = iter([(90, 90), (51, 85), (32, 80)])

    def fake_get(url, params=None, timeout=None):
        captured["key"] = params["key"]
        current, free = next(ratios)
        return _flow_response(current, free)

    monkeypatch.setattr(httpx, "get", fake_get)
    result = live_road.fetch_corridor_congestion()
    assert result["source"] == "tomtom"
    assert result["live"] is True
    assert result["worst_ratio"] == round(32 / 80, 3)
    assert [p["label"] for p in result["points"]] == [
        "Rotterdam",
        "Hamburg",
        "Oslo approach",
    ]
    assert captured["key"] == os.environ["TOMTOM_API_KEY"]


def test_road_falls_back_labeled_when_call_fails(monkeypatch):
    _set_phase2_env(monkeypatch)

    def error_get(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", error_get)
    result = live_road.fetch_corridor_congestion()
    assert result["source"] == "synthetic-fallback"
    assert result["live"] is False


def test_rail_setup_required_without_key(monkeypatch):
    _clear_phase2_env(monkeypatch)
    _no_network(monkeypatch)
    result = live_rail.fetch_network_disruptions()
    assert result["source"] == "setup-required"
    assert result["live"] is False
    assert "NS_API_KEY" in result["detail"]


def test_rail_live_counts_active_and_rotterdam(monkeypatch):
    _set_phase2_env(monkeypatch)
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["headers"] = headers
        captured["params"] = params
        return httpx.Response(
            200,
            json=[
                {"id": "1", "type": "disruption", "title": "Storing Amsterdam-Utrecht"},
                {
                    "id": "2",
                    "type": "disruption",
                    "title": "Werkzaamheden Rotterdam Centraal",
                },
                {"id": "3", "type": "maintenance", "title": "Onderhoud Groningen"},
            ],
            request=httpx.Request("GET", live_rail.DISRUPTIONS_URL),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    result = live_rail.fetch_network_disruptions()
    assert result["source"] == "ns-disruptions"
    assert result["live"] is True
    assert result["active_count"] == 3
    assert result["rotterdam_count"] == 1
    assert captured["headers"] == {
        "Ocp-Apim-Subscription-Key": os.environ["NS_API_KEY"]
    }
    assert captured["params"] == {"isActive": "true"}


def test_rail_falls_back_labeled_when_call_fails(monkeypatch):
    _set_phase2_env(monkeypatch)

    def error_get(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", error_get)
    result = live_rail.fetch_network_disruptions()
    assert result["source"] == "synthetic-fallback"
    assert result["live"] is False


def _route_all_live(
    monkeypatch, ams=12, osl=3, ratios=(1.0, 1.0, 1.0), disruptions=()
):
    """Route all five live clients (sea + Phase 2) with one fake transport."""

    def fake_post(url, data=None, timeout=None):
        return httpx.Response(
            200,
            json={"access_token": "route-all-live-sample"},
            request=httpx.Request("POST", live_air.TOKEN_URL),
        )

    ratios_iter = iter(ratios)

    def fake_get(url, params=None, headers=None, timeout=None):
        text = str(url)
        if "marine-api" in text:
            return _ok_marine(0.4)
        if "api.open-meteo" in text:
            return _ok_wind(45.0)
        if "opensky" in text:
            count = ams if params["lamin"] < 55 else osl
            tag = "ams" if params["lamin"] < 55 else "osl"
            return _states_response([_state(f"{tag}{i}") for i in range(count)])
        if "tomtom" in text:
            ratio = next(ratios_iter)
            return _flow_response(90 * ratio, 90)
        assert "apiportal.ns.nl" in text
        return httpx.Response(
            200,
            json=list(disruptions),
            request=httpx.Request("GET", live_rail.DISRUPTIONS_URL),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", fake_get)


def test_snapshot_unconfigured_matches_baseline_plus_setup_states(monkeypatch):
    _clear_phase2_env(monkeypatch)

    def error_get(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", error_get)
    body = run_live_snapshot()
    baseline = run_demo()
    assert body["findings"] == baseline["findings"]
    assert body["ranked_options"] == baseline["ranked_options"]
    assert body["air"]["source"] == "setup-required"
    assert body["road"]["source"] == "setup-required"
    assert body["rail"]["source"] == "setup-required"
    assert body["provenance"]["air"]["delay_hours"] == "synthetic"
    assert body["provenance"]["road"]["delay_hours"] == "synthetic"
    assert body["provenance"]["rail"]["delay_hours"] == "synthetic"


def test_snapshot_live_phase2_overrides_all_legs(monkeypatch):
    _set_phase2_env(monkeypatch)
    _route_all_live(monkeypatch)
    body = north_sea_storm_live()
    by_mode = {f["mode"]: f for f in body["findings"]}
    assert by_mode["air"]["delay_hours"] == 4
    assert by_mode["road"]["delay_hours"] == 6
    assert by_mode["rail"]["delay_hours"] == 4
    assert body["ranked_options"][0]["option_id"] == "sea-wait"
    assert body["provenance"]["air"]["airborne_ams"] == "measured"
    assert body["provenance"]["air"]["delay_hours"] == "estimated-from-conditions"
    assert body["provenance"]["road"]["worst_congestion_ratio"] == "measured"
    assert body["provenance"]["road"]["delay_hours"] == "estimated-from-conditions"
    assert body["provenance"]["rail"]["active_disruptions"] == "measured"
    assert body["provenance"]["rail"]["delay_hours"] == "estimated-from-conditions"
    assert body["provenance"]["air"]["cost_usd"] == "synthetic"


def test_snapshot_zero_airborne_declines_estimate(monkeypatch):
    _set_phase2_env(monkeypatch)
    _route_all_live(monkeypatch, ams=0, osl=0)
    body = run_live_snapshot()
    air = next(f for f in body["findings"] if f["mode"] == "air")
    assert air["delay_hours"] == 4  # synthetic stands; zero traffic is ambiguous
    assert body["provenance"]["air"]["airborne_ams"] == "measured"
    assert body["provenance"]["air"]["delay_hours"] == "synthetic"


def test_snapshot_thin_air_traffic_advises_delay(monkeypatch):
    _set_phase2_env(monkeypatch)
    _route_all_live(monkeypatch, ams=2, osl=1)
    body = run_live_snapshot()
    air = next(f for f in body["findings"] if f["mode"] == "air")
    assert air["delay_hours"] == 8
    assert air["status"] == "available"


def test_snapshot_congested_road_degrades_finding(monkeypatch):
    _set_phase2_env(monkeypatch)
    _route_all_live(monkeypatch, ratios=(0.9, 0.6, 0.3))
    body = run_live_snapshot()
    road = next(f for f in body["findings"] if f["mode"] == "road")
    assert road["delay_hours"] == 14
    assert road["status"] == "degraded"


def test_snapshot_rotterdam_disruption_degrades_rail(monkeypatch):
    _set_phase2_env(monkeypatch)
    _route_all_live(
        monkeypatch,
        disruptions=(
            {"id": "9", "type": "disruption", "title": "Sein storing Rotterdam"},
        ),
    )
    body = run_live_snapshot()
    rail = next(f for f in body["findings"] if f["mode"] == "rail")
    assert rail["delay_hours"] == 12
    assert rail["status"] == "degraded"


def test_snapshot_network_disruption_advises_rail(monkeypatch):
    _set_phase2_env(monkeypatch)
    _route_all_live(
        monkeypatch,
        disruptions=(
            {"id": "7", "type": "disruption", "title": "Storing Amsterdam-Utrecht"},
        ),
    )
    body = run_live_snapshot()
    rail = next(f for f in body["findings"] if f["mode"] == "rail")
    assert rail["delay_hours"] == 8
    assert rail["status"] == "available"


def test_grid_page_mentions_phase2_layers():
    html = render_grid_page()
    assert "Phase 2 air, road, and rail layers" in html
    assert "OpenSky" in html
    assert "TomTom" in html
    assert "setup-required" in html
