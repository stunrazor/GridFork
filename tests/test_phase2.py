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


def _adsb_response(aircraft, now=OPEN_SKY_TIME):
    return httpx.Response(
        200,
        json={"ac": aircraft, "total": len(aircraft), "now": now},
        request=httpx.Request("GET", "https://api.adsb.lol/v2/x"),
    )


def _ac(alt_baro=10000, flight="KLM123"):
    aircraft = {"hex": "abc123", "flight": flight, "lat": 52.3, "lon": 4.7}
    if alt_baro is not None:
        aircraft["alt_baro"] = alt_baro
    return aircraft


def test_adsb_live_counts_airborne_per_airport(monkeypatch):
    captured = []

    def fake_get(url, params=None, timeout=None):
        captured.append(str(url))
        if "4.76" in str(url):
            return _adsb_response(
                [_ac(12000), _ac(8000), _ac(0), _ac(None)]
            )
        return _adsb_response([_ac(15000)])

    monkeypatch.setattr(httpx, "get", fake_get)
    result = live_air.fetch_adsb_traffic()
    assert result["source"] == "adsb-lol"
    assert result["live"] is True
    assert result["airborne_ams"] == 2  # ground-level and unknown excluded
    assert result["airborne_osl"] == 1
    assert len(captured) == 2


def test_adsb_uses_base_url_override(monkeypatch):
    monkeypatch.setenv("ADSB_BASE_URL", "https://relay.example/")
    captured = []

    def fake_get(url, params=None, timeout=None):
        captured.append(str(url))
        return _adsb_response([_ac()])

    monkeypatch.setattr(httpx, "get", fake_get)
    result = live_air.fetch_adsb_traffic()
    assert result["live"] is True
    assert captured == [
        "https://relay.example/v2/lat/52.31/lon/4.76/dist/25",
        "https://relay.example/v2/lat/60.19/lon/11.1/dist/25",
    ]


def test_adsb_handles_millisecond_timestamps(monkeypatch):
    # Live adsb.lol returns "now" in milliseconds; naive seconds parsing
    # overflows and must not sink the readout.
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **k: _adsb_response([_ac()], now=OPEN_SKY_TIME * 1000),
    )
    result = live_air.fetch_adsb_traffic()
    assert result["live"] is True
    assert result["observed_at"] == (
        datetime.fromtimestamp(OPEN_SKY_TIME, tz=timezone.utc).isoformat()
    )


def test_adsb_falls_back_labeled_when_call_fails(monkeypatch):
    def error_get(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", error_get)
    result = live_air.fetch_adsb_traffic()
    assert result["source"] == "synthetic-fallback"
    assert result["live"] is False
    assert result["detail"] == "ConnectError"


def test_air_uses_keyless_adsb_without_credentials(monkeypatch):
    _clear_phase2_env(monkeypatch)
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: _adsb_response([_ac()])
    )
    result = live_air.fetch_air_traffic()
    assert result["source"] == "adsb-lol"
    assert result["live"] is True


def test_air_prefers_opensky_over_adsb(monkeypatch):
    _set_phase2_env(monkeypatch)
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, data=None, timeout=None: httpx.Response(
            200,
            json={"access_token": "prefer-opensky-sample"},
            request=httpx.Request("POST", live_air.TOKEN_URL),
        ),
    )

    def fake_get(url, params=None, headers=None, timeout=None):
        assert "adsb.lol" not in str(url), "must not touch adsb.lol"
        return _states_response([_state("ok1")])

    monkeypatch.setattr(httpx, "get", fake_get)
    result = live_air.fetch_air_traffic()
    assert result["source"] == "opensky"


def test_air_falls_through_to_adsb_when_opensky_fails(monkeypatch):
    _set_phase2_env(monkeypatch)

    def error_post(*args, **kwargs):
        raise httpx.ConnectError("opensky unreachable")

    def fake_get(url, params=None, headers=None, timeout=None):
        assert "adsb.lol" in str(url)
        return _adsb_response([_ac(), _ac()])

    monkeypatch.setattr(httpx, "post", error_post)
    monkeypatch.setattr(httpx, "get", fake_get)
    result = live_air.fetch_air_traffic()
    assert result["source"] == "adsb-lol"
    assert result["airborne_ams"] == 2


def test_snapshot_adsb_live_drives_air_leg(monkeypatch):
    _clear_phase2_env(monkeypatch)

    def fake_get(url, params=None, headers=None, timeout=None):
        text = str(url)
        if "marine-api" in text:
            return _ok_marine(0.4)
        if "api.open-meteo" in text:
            return _ok_wind(45.0)
        assert "adsb.lol" in text
        return _adsb_response([_ac() for _ in range(6)])

    monkeypatch.setattr(httpx, "get", fake_get)
    body = run_live_snapshot()
    air = next(f for f in body["findings"] if f["mode"] == "air")
    assert air["delay_hours"] == 4  # 6 + 6 airborne across both boxes
    assert body["air"]["source"] == "adsb-lol"
    assert body["provenance"]["air"]["airborne_ams"] == "measured"


def test_air_falls_back_labeled_when_call_fails(monkeypatch):
    _set_phase2_env(monkeypatch)

    def error_post(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "post", error_post)
    result = live_air.fetch_corridor_traffic()
    assert result["source"] == "synthetic-fallback"
    assert result["live"] is False
    assert result["detail"] == "ConnectError"


def test_air_fallback_detail_reports_http_status(monkeypatch):
    _set_phase2_env(monkeypatch)

    def denied_post(*args, **kwargs):
        request = httpx.Request("POST", live_air.TOKEN_URL)
        return httpx.Response(401, request=request)

    def denied_get(*args, **kwargs):
        raise AssertionError("must not query states without a token")

    monkeypatch.setattr(httpx, "post", denied_post)
    monkeypatch.setattr(httpx, "get", denied_get)
    result = live_air.fetch_corridor_traffic()
    assert result["source"] == "synthetic-fallback"
    assert result["detail"] == "HTTPStatusError 401"


def test_road_setup_required_without_key(monkeypatch):
    _clear_phase2_env(monkeypatch)
    _no_network(monkeypatch)
    result = live_road.fetch_corridor_congestion()
    assert result["source"] == "setup-required"
    assert result["live"] is False
    assert "TOMTOM_API_KEY" in result["detail"]


def _incident(icon=6, magnitude=2, desc="Jam on E6"):
    return {
        "properties": {
            "iconCategory": icon,
            "magnitudeOfDelay": magnitude,
            "events": [{"description": desc}],
        }
    }


def _incidents_response(incidents):
    return httpx.Response(
        200,
        json={"incidents": incidents},
        request=httpx.Request("GET", live_road.INCIDENTS_URL),
    )


def _route_response(length_m=1410000, travel_s=22 * 3600, delay_s=0):
    return httpx.Response(
        200,
        json={
            "routes": [
                {
                    "summary": {
                        "lengthInMeters": length_m,
                        "travelTimeInSeconds": travel_s,
                        "trafficDelayInSeconds": delay_s,
                    }
                }
            ]
        },
        request=httpx.Request("GET", "https://api.tomtom.com/routing/1/x"),
    )


def test_road_live_reports_worst_ratio(monkeypatch):
    _set_phase2_env(monkeypatch)
    captured = {}
    ratios = iter([(90, 90), (51, 85), (32, 80)])

    def fake_get(url, params=None, timeout=None):
        text = str(url)
        if "incidentDetails" in text:
            return _incidents_response([])
        if "routing/1" in text:
            return _route_response()
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


def test_road_live_includes_incidents_and_route(monkeypatch):
    _set_phase2_env(monkeypatch)
    captured = {}
    boxes = iter(
        [
            [_incident(icon=8, magnitude=4, desc="Road closed A16")],
            [_incident(icon=1, magnitude=3, desc="Accident A1")],
            [],
        ]
    )

    def fake_get(url, params=None, timeout=None):
        text = str(url)
        if "incidentDetails" in text:
            captured.setdefault("incident_params", params)
            return _incidents_response(next(boxes))
        if "routing/1" in text:
            captured["route_url"] = text
            captured["route_params"] = params
            return _route_response(
                length_m=1425000, travel_s=23 * 3600, delay_s=int(2.5 * 3600)
            )
        return _flow_response(90, 90)

    monkeypatch.setattr(httpx, "get", fake_get)
    result = live_road.fetch_corridor_congestion()
    assert result["incidents"]["count"] == 2
    assert result["incidents"]["closures"] == 1
    assert result["incidents"]["majors"] == 2
    assert result["incidents"]["sample"] == ["Road closed A16", "Accident A1"]
    assert result["route"]["distance_km"] == 1425
    assert result["route"]["transit_hours"] == 23.0
    assert result["route"]["traffic_delay_hours"] == 2.5
    assert "bbox" in captured["incident_params"]
    assert captured["incident_params"]["timeValidityFilter"] == "present"
    assert "fields" in captured["incident_params"]
    assert "calculateRoute" in captured["route_url"]
    assert captured["route_params"]["travelMode"] == "truck"
    assert captured["route_params"]["traffic"] == "true"


def test_road_survives_incident_and_route_failures(monkeypatch):
    _set_phase2_env(monkeypatch)

    def fake_get(url, params=None, timeout=None):
        text = str(url)
        if "incidentDetails" in text or "routing/1" in text:
            raise httpx.ConnectError("partial outage")
        return _flow_response(90, 90)

    monkeypatch.setattr(httpx, "get", fake_get)
    result = live_road.fetch_corridor_congestion()
    assert result["live"] is True
    assert result["worst_ratio"] == 1.0
    assert result["incidents"] is None
    assert result["route"] is None


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
    monkeypatch,
    ams=12,
    osl=3,
    ratios=(1.0, 1.0, 1.0),
    disruptions=(),
    incident_boxes=None,
    route_delay_s=0,
):
    """Route all live clients (sea + Phase 2 + road extras) with one double."""

    def fake_post(url, data=None, timeout=None):
        return httpx.Response(
            200,
            json={"access_token": "route-all-live-sample"},
            request=httpx.Request("POST", live_air.TOKEN_URL),
        )

    ratios_iter = iter(ratios)
    boxes_iter = iter(
        incident_boxes if incident_boxes is not None else [[], [], []]
    )

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
        if "incidentDetails" in text:
            return _incidents_response(next(boxes_iter))
        if "routing/1" in text:
            return _route_response(delay_s=route_delay_s)
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
    monkeypatch.delenv("DB_CLIENT_ID", raising=False)
    monkeypatch.delenv("DB_API_KEY", raising=False)

    def error_http(*args, **kwargs):
        raise httpx.ConnectError("offline")

    # Keyless layers (sea, adsb.lol air, Entur rail) attempt and fall
    # back labeled; keyed layers report setup-required without any call.
    monkeypatch.setattr(httpx, "get", error_http)
    monkeypatch.setattr(httpx, "post", error_http)
    body = run_live_snapshot()
    baseline = run_demo()
    assert body["findings"] == baseline["findings"]
    assert body["ranked_options"] == baseline["ranked_options"]
    assert body["air"]["source"] == "synthetic-fallback"
    assert body["road"]["source"] == "setup-required"
    assert body["rail"]["source"] == "synthetic-fallback"
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


def test_snapshot_closure_floors_road_when_congested(monkeypatch):
    _set_phase2_env(monkeypatch)
    _route_all_live(
        monkeypatch,
        ratios=(0.9, 0.6, 0.3),
        incident_boxes=[
            [_incident(icon=8, magnitude=4, desc="Road closed A16")],
            [],
            [],
        ],
    )
    body = run_live_snapshot()
    road = next(f for f in body["findings"] if f["mode"] == "road")
    assert road["delay_hours"] == 14
    assert road["status"] == "degraded"
    assert body["provenance"]["road"]["closure_count"] == "measured"


def test_snapshot_major_incident_floors_road_when_congested(monkeypatch):
    _set_phase2_env(monkeypatch)
    _route_all_live(
        monkeypatch,
        ratios=(0.9, 0.7, 0.85),  # worst 0.7: base 10, corroborates
        incident_boxes=[
            [_incident(icon=1, magnitude=3, desc="Accident A1")],
            [],
            [],
        ],
    )
    body = run_live_snapshot()
    road = next(f for f in body["findings"] if f["mode"] == "road")
    assert road["delay_hours"] == 12
    assert road["status"] == "degraded"


def test_snapshot_free_flow_ignores_metro_closures(monkeypatch):
    # Live-learned: metros report hundreds of closures while the corridor
    # itself runs free; uncorroborated counts stay advisory context.
    _set_phase2_env(monkeypatch)
    _route_all_live(
        monkeypatch,
        incident_boxes=[
            [_incident(icon=8, magnitude=4, desc="Road closed A16")],
            [_incident(icon=8, magnitude=4, desc="Road closed B5")],
            [],
        ],
    )
    body = run_live_snapshot()
    road = next(f for f in body["findings"] if f["mode"] == "road")
    assert road["delay_hours"] == 6
    assert road["status"] == "available"
    assert body["provenance"]["road"]["closure_count"] == "measured"


def test_snapshot_routed_delay_corroborates_closure(monkeypatch):
    _set_phase2_env(monkeypatch)
    _route_all_live(
        monkeypatch,
        incident_boxes=[
            [_incident(icon=8, magnitude=4, desc="Road closed A16")],
            [],
            [],
        ],
        route_delay_s=2 * 3600,
    )
    body = run_live_snapshot()
    road = next(f for f in body["findings"] if f["mode"] == "road")
    assert road["delay_hours"] == 14
    assert road["status"] == "degraded"


def test_snapshot_routed_traffic_delay_raises_road(monkeypatch):
    _set_phase2_env(monkeypatch)
    _route_all_live(monkeypatch, route_delay_s=9 * 3600)
    body = run_live_snapshot()
    road = next(f for f in body["findings"] if f["mode"] == "road")
    assert road["delay_hours"] == 9
    assert body["provenance"]["road"]["traffic_delay_hours"] == "measured"


def test_snapshot_routed_transit_overwrites_synthetic(monkeypatch):
    _set_phase2_env(monkeypatch)
    _route_all_live(monkeypatch)
    body = run_live_snapshot()
    road = next(f for f in body["findings"] if f["mode"] == "road")
    assert "1410" in road["summary"]  # routed km replace synthetic 1400
    assert body["provenance"]["road"]["distance_km"] == "measured"
    assert body["provenance"]["road"]["transit_hours"] == "measured"


DB_FCHG_XML = """<timetable station="Hamburg Hbf" evaNo="8002549">
  <s id="1"><ar pt="2611011200" ct="2611011245"/><dp pt="2611011210" ct="2611011255"/></s>
  <s id="2"><dp pt="2611011300" ct="2611011300" cs="c"/></s>
  <s id="3"><ar pt="2611011400" cp="7"/></s>
</timetable>"""


def _db_response(xml=DB_FCHG_XML):
    return httpx.Response(
        200,
        text=xml,
        request=httpx.Request("GET", "https://apis.deutschebahn.com/db-x"),
    )


def _set_db_env(monkeypatch):
    monkeypatch.setenv("DB_CLIENT_ID", "unit-db-id")
    monkeypatch.setenv("DB_API_KEY", "unit-db-key")


def test_db_setup_required_without_keys(monkeypatch):
    _clear_phase2_env(monkeypatch)
    monkeypatch.delenv("DB_CLIENT_ID", raising=False)
    monkeypatch.delenv("DB_API_KEY", raising=False)
    _no_network(monkeypatch)
    result = live_rail.fetch_db_disruptions()
    assert result["source"] == "setup-required"
    assert result["live"] is False
    assert "DB_CLIENT_ID" in result["detail"]


def test_db_live_counts_disrupted_and_cancelled(monkeypatch):
    _set_db_env(monkeypatch)
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = str(url)
        captured["headers"] = headers
        return _db_response()

    monkeypatch.setattr(httpx, "get", fake_get)
    result = live_rail.fetch_db_disruptions()
    assert result["source"] == "db-timetables"
    assert result["live"] is True
    assert result["active_count"] == 2  # delayed stop + cancelled stop
    assert result["severe_count"] == 1  # platform-only change ignored
    assert captured["url"].endswith("/fchg/8002549")
    assert captured["headers"] == {
        "DB-Client-Id": os.environ["DB_CLIENT_ID"],
        "DB-Api-Key": os.environ["DB_API_KEY"],
    }


def test_db_falls_back_labeled_when_call_fails(monkeypatch):
    _set_db_env(monkeypatch)

    def error_get(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", error_get)
    result = live_rail.fetch_db_disruptions()
    assert result["source"] == "synthetic-fallback"
    assert result["live"] is False


def test_rail_prefers_ns_over_db(monkeypatch):
    _set_phase2_env(monkeypatch)
    _set_db_env(monkeypatch)

    def fake_get(url, params=None, headers=None, timeout=None):
        assert "apiportal.ns.nl" in str(url), "must not touch DB when NS is keyed"
        return httpx.Response(
            200,
            json=[],
            request=httpx.Request("GET", live_rail.DISRUPTIONS_URL),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    result = live_rail.fetch_rail_disruptions()
    assert result["source"] == "ns-disruptions"
    assert result["live"] is True


def test_rail_falls_back_to_db_without_ns_key(monkeypatch):
    _clear_phase2_env(monkeypatch)
    _set_db_env(monkeypatch)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _db_response())
    result = live_rail.fetch_rail_disruptions()
    assert result["source"] == "db-timetables"
    assert result["live"] is True
    assert result["active_count"] == 2
    assert result["severe_count"] == 1


def _entur_response(calls):
    return httpx.Response(
        200,
        json={"data": {"stopPlace": {"estimatedCalls": calls}}},
        request=httpx.Request("POST", live_rail.ENTUR_URL),
    )


def _call(aimed, expected=None, cancelled=False):
    return {
        "aimedDepartureTime": aimed,
        "expectedDepartureTime": expected or aimed,
        "cancellation": cancelled,
        "realtime": True,
    }


def test_entur_live_counts_delayed_and_cancelled(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = str(url)
        captured["headers"] = headers
        captured["query"] = json["query"]
        return _entur_response(
            [
                _call("2026-11-01T08:00:00+01:00", "2026-11-01T08:25:00+01:00"),
                _call("2026-11-01T08:10:00+01:00", cancelled=True),
                _call("2026-11-01T08:20:00+01:00", "2026-11-01T08:22:00+01:00"),
            ]
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = live_rail.fetch_entur_disruptions()
    assert result["source"] == "entur"
    assert result["live"] is True
    assert result["active_count"] == 2  # 25-min delay + cancellation
    assert result["severe_count"] == 1  # 2-min delay is routine, not counted
    assert captured["url"] == live_rail.ENTUR_URL
    assert captured["headers"]["ET-Client-Name"] == "stunrazor-gridfork"
    assert "NSR:StopPlace:59872" in captured["query"]


def test_entur_falls_back_labeled_on_graphql_errors(monkeypatch):
    def fake_post(*args, **kwargs):
        return httpx.Response(
            200,
            json={"errors": [{"message": "client unknown"}]},
            request=httpx.Request("POST", live_rail.ENTUR_URL),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = live_rail.fetch_entur_disruptions()
    assert result["source"] == "synthetic-fallback"
    assert result["live"] is False


def test_rail_uses_keyless_entur_without_keys(monkeypatch):
    _clear_phase2_env(monkeypatch)
    monkeypatch.delenv("DB_CLIENT_ID", raising=False)
    monkeypatch.delenv("DB_API_KEY", raising=False)
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _entur_response([_call("2026-11-01T08:00:00+01:00")])
    )
    result = live_rail.fetch_rail_disruptions()
    assert result["source"] == "entur"
    assert result["live"] is True


def test_rail_falls_through_to_entur_when_keyed_providers_fail(monkeypatch):
    _set_phase2_env(monkeypatch)
    _set_db_env(monkeypatch)

    def error_get(*args, **kwargs):
        raise httpx.ConnectError("both keyed providers down")

    monkeypatch.setattr(httpx, "get", error_get)
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _entur_response([_call("2026-11-01T08:00:00+01:00")])
    )
    result = live_rail.fetch_rail_disruptions()
    assert result["source"] == "entur"
    assert result["live"] is True


def test_rail_reports_fallback_when_all_providers_fail(monkeypatch):
    _set_phase2_env(monkeypatch)
    _set_db_env(monkeypatch)

    def error_http(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", error_http)
    monkeypatch.setattr(httpx, "post", error_http)
    result = live_rail.fetch_rail_disruptions()
    assert result["source"] == "synthetic-fallback"
    assert result["live"] is False
    assert result["active_count"] is None
    assert result["severe_count"] is None


def test_rail_prefers_db_over_entur(monkeypatch):
    _clear_phase2_env(monkeypatch)
    _set_db_env(monkeypatch)

    def explode_post(*args, **kwargs):
        raise AssertionError("must not touch Entur when DB is keyed")

    monkeypatch.setattr(httpx, "post", explode_post)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _db_response())
    result = live_rail.fetch_rail_disruptions()
    assert result["source"] == "db-timetables"


def test_snapshot_entur_cancellation_degrades_rail(monkeypatch):
    _clear_phase2_env(monkeypatch)
    monkeypatch.delenv("DB_CLIENT_ID", raising=False)
    monkeypatch.delenv("DB_API_KEY", raising=False)

    def fake_get(url, params=None, headers=None, timeout=None):
        text = str(url)
        if "marine-api" in text:
            return _ok_marine(0.4)
        return _ok_wind(45.0)

    def fake_post(url, json=None, headers=None, timeout=None):
        assert "entur" in str(url)
        return _entur_response(
            [_call("2026-11-01T08:10:00+01:00", cancelled=True)]
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    body = run_live_snapshot()
    rail = next(f for f in body["findings"] if f["mode"] == "rail")
    assert rail["delay_hours"] == 12
    assert rail["status"] == "degraded"
    assert body["rail"]["source"] == "entur"
    assert body["provenance"]["rail"]["severe_disruptions"] == "measured"


def test_snapshot_db_cancellation_degrades_rail(monkeypatch):
    _clear_phase2_env(monkeypatch)
    _set_db_env(monkeypatch)

    def fake_get(url, params=None, headers=None, timeout=None):
        text = str(url)
        if "marine-api" in text:
            return _ok_marine(0.4)
        if "api.open-meteo" in text:
            return _ok_wind(45.0)
        assert "deutschebahn" in text
        return _db_response()

    monkeypatch.setattr(httpx, "get", fake_get)
    body = run_live_snapshot()
    rail = next(f for f in body["findings"] if f["mode"] == "rail")
    assert rail["delay_hours"] == 12
    assert rail["status"] == "degraded"
    assert body["rail"]["source"] == "db-timetables"
    assert body["provenance"]["rail"]["severe_disruptions"] == "measured"


def test_snapshot_db_quiet_network_means_normal_rail(monkeypatch):
    _clear_phase2_env(monkeypatch)
    _set_db_env(monkeypatch)

    def fake_get(url, params=None, headers=None, timeout=None):
        text = str(url)
        if "marine-api" in text:
            return _ok_marine(0.4)
        if "api.open-meteo" in text:
            return _ok_wind(45.0)
        return _db_response("<timetable station=\"Hamburg Hbf\"/>")

    monkeypatch.setattr(httpx, "get", fake_get)
    body = run_live_snapshot()
    rail = next(f for f in body["findings"] if f["mode"] == "rail")
    assert rail["delay_hours"] == 4
    assert rail["status"] == "available"


def test_grid_page_mentions_phase2_layers():
    html = render_grid_page()
    assert "Phase 2 air, road, and rail layers" in html
    assert "OpenSky" in html
    assert "TomTom" in html
    assert "setup-required" in html
