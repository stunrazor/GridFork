"""Tests for the live weather layer (fully mocked, no network)."""

import httpx

import live_weather
from main import north_sea_storm_weather


def _ok_response():
    return httpx.Response(
        200,
        json={"current": {"time": "2026-10-30T15:15", "wind_speed_10m": 12.5}},
        request=httpx.Request("GET", live_weather.FORECAST_URL),
    )


def test_fetch_returns_live_wind_in_kph(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return _ok_response()

    monkeypatch.setattr(live_weather.httpx, "get", fake_get)
    result = live_weather.fetch_rotterdam_wind()
    assert result == {
        "source": "open-meteo",
        "live": True,
        "wind_kph": 45.0,
        "observed_at": "2026-10-30T15:15",
    }
    assert captured["params"]["latitude"] == 51.95


def test_fetch_falls_back_labeled_on_error(monkeypatch):
    def error_get(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(live_weather.httpx, "get", error_get)
    result = live_weather.fetch_rotterdam_wind()
    assert result["source"] == "synthetic-fallback"
    assert result["live"] is False


def test_weather_endpoint_function_shape(monkeypatch):
    monkeypatch.setattr(
        live_weather.httpx, "get", lambda *a, **k: _ok_response()
    )
    body = north_sea_storm_weather()
    assert body["source"] == "open-meteo"
    assert body["wind_kph"] == 45.0
