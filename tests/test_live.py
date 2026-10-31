"""Tests for the live-snapshot path (fully mocked, no network)."""

import httpx

import live_marine
import live_weather
from grid_page import render_grid_page
from main import north_sea_storm_live
from orchestrator import build_live_scenario, run_demo, run_live_snapshot


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


def _route_live(monkeypatch, wave_height, wind_kph):
    """Install one fake GET dispatching marine vs wind by URL.

    Both clients share the global httpx module, so two separate patches
    would overwrite each other; a single router is the honest double.
    """

    def fake_get(url, params=None, timeout=None):
        if "marine-api" in str(url):
            return _ok_marine(wave_height)
        return _ok_wind(wind_kph)

    monkeypatch.setattr(live_marine.httpx, "get", fake_get)


def test_marine_fetch_returns_live_wave_height(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _ok_marine(0.4)

    monkeypatch.setattr(live_marine.httpx, "get", fake_get)
    result = live_marine.fetch_north_sea_waves()
    assert result == {
        "source": "open-meteo",
        "live": True,
        "wave_height_m": 0.4,
        "observed_at": "2026-10-31T19:15",
    }
    assert captured["url"] == "https://marine-api.open-meteo.com/v1/marine"
    assert captured["params"]["current"] == "wave_height"


def test_marine_fetch_falls_back_labeled_on_error(monkeypatch):
    def error_get(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(live_marine.httpx, "get", error_get)
    result = live_marine.fetch_north_sea_waves()
    assert result["source"] == "synthetic-fallback"
    assert result["live"] is False
    assert result["wave_height_m"] == 8.5


def test_live_calm_seas_make_sailing_top_pick(monkeypatch):
    _route_live(monkeypatch, 0.4, 45.0)
    body = run_live_snapshot()
    assert body["data_mode"] == "live-snapshot"
    assert body["synthetic"] is False
    sea = next(f for f in body["findings"] if f["mode"] == "sea")
    assert sea["status"] == "available"
    assert sea["delay_hours"] == 2
    assert body["ranked_options"][0]["option_id"] == "sea-wait"
    assert body["provenance"]["sea"]["wave_height_m"] == "measured"
    assert body["provenance"]["sea"]["wind_kph"] == "measured"
    assert body["provenance"]["sea"]["delay_hours"] == "estimated-from-conditions"
    assert body["provenance"]["sea"]["cost_usd"] == "synthetic-estimate"


def test_live_storm_matches_synthetic_scale(monkeypatch):
    _route_live(monkeypatch, 9.0, 120.0)
    body = run_live_snapshot()
    sea = next(f for f in body["findings"] if f["mode"] == "sea")
    assert sea["status"] == "disrupted"
    assert sea["delay_hours"] == 48
    assert body["ranked_options"][0]["option_id"] == "rail-reroute"


def test_snapshot_falls_back_to_baseline_offline(monkeypatch):
    def error_get(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(live_marine.httpx, "get", error_get)
    monkeypatch.setattr(live_weather.httpx, "get", error_get)
    body = run_live_snapshot()
    baseline = run_demo()
    assert body["ranked_options"] == baseline["ranked_options"]
    assert body["findings"] == baseline["findings"]
    assert body["provenance"]["sea"]["wave_height_m"] == "synthetic-fallback"
    assert body["marine"]["live"] is False
    assert body["wind"]["live"] is False


def test_live_scenario_marks_other_modes_synthetic(monkeypatch):
    _route_live(monkeypatch, 0.4, 45.0)
    _, provenance, _, _ = build_live_scenario()
    assert provenance["air"]["delay_hours"] == "synthetic"
    assert provenance["road"]["delay_hours"] == "synthetic"
    assert provenance["rail"]["delay_hours"] == "synthetic"


def test_live_endpoint_shape(monkeypatch):
    _route_live(monkeypatch, 0.4, 45.0)
    body = north_sea_storm_live()
    assert body["data_mode"] == "live-snapshot"
    assert len(body["ranked_options"]) == 4
    assert "provenance" in body


def test_grid_page_has_live_snapshot_section():
    html = render_grid_page()
    assert "Live snapshot" in html
    assert "Run live snapshot" in html
    assert "measured" in html.lower()
    script = html.split("<script>", 1)[1]
    assert script.count("/demo/north-sea-storm/live") == 1
