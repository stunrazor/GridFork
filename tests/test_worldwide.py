"""Tests for worldwide snapshots: geo helpers, presets, builder, endpoint.

Every test is hermetic: live clients are patched at the fetch-function
seam, and the two geo network calls (Nominatim, Entur bbox) use rigged
httpx responses.
"""

import httpx
import pytest

import geo
import live_air
import live_marine
import live_rail
import live_road
import live_weather
import snapshot as snapshot_mod
from main import world_snapshot

OSLO = {"name": "Oslo", "lat": 59.91, "lon": 10.75}
ROTTERDAM = {"name": "Rotterdam", "lat": 51.95, "lon": 4.14}


def _patch_live_layers(
    monkeypatch,
    wave=0.4,
    wind=20.0,
    air_origin=8,
    air_dest=4,
    ratio=1.0,
    route=None,
    disruptions=0,
):
    """Rig every live client a snapshot touches."""
    monkeypatch.setattr(
        live_marine,
        "fetch_waves_at",
        lambda lat, lon, timeout=10.0: {
            "source": "open-meteo",
            "live": True,
            "wave_height_m": wave,
            "observed_at": "2026-11-02T00:00",
        },
    )
    monkeypatch.setattr(
        live_weather,
        "fetch_wind_at",
        lambda lat, lon, timeout=10.0: {
            "source": "open-meteo",
            "live": True,
            "wind_kph": wind,
            "observed_at": "2026-11-02T00:00",
        },
    )
    monkeypatch.setattr(
        live_air,
        "fetch_air_traffic",
        lambda timeout=10.0, boxes=None, points=None: {
            "source": "adsb-lol",
            "live": True,
            "airborne_origin": air_origin,
            "airborne_dest": air_dest,
            "observed_at": "2026-11-02T00:00+00:00",
        },
    )
    monkeypatch.setattr(
        live_road,
        "fetch_corridor_congestion",
        lambda timeout=10.0, points=(), origin=(), dest=(): {
            "source": "tomtom",
            "live": True,
            "worst_ratio": ratio,
            "points": [{"label": "p", "ratio": ratio}],
            "incidents": None,
            "route": route,
            "observed_at": None,
        },
    )
    monkeypatch.setattr(
        live_rail,
        "fetch_entur_disruptions",
        lambda timeout=10.0, stop_id="x": {
            "source": "entur",
            "live": True,
            "active_count": disruptions,
            "severe_count": 0,
            "observed_at": None,
        },
    )
    monkeypatch.setattr(
        geo, "nearest_entur_stop", lambda lat, lon, timeout=10.0: ("stop", "Oslo S")
    )


def _patch_offline(monkeypatch):
    """Rig every live client to fail; geo lookups find nothing."""

    def explode(*args, **kwargs):
        raise AssertionError("offline snapshot must not touch the network")

    monkeypatch.setattr(httpx, "get", explode)
    monkeypatch.setattr(httpx, "post", explode)
    monkeypatch.setattr(
        live_marine,
        "fetch_waves_at",
        lambda lat, lon, timeout=10.0: {
            "source": "synthetic-fallback",
            "live": False,
            "wave_height_m": 1.0,
            "observed_at": None,
        },
    )
    monkeypatch.setattr(
        live_weather,
        "fetch_wind_at",
        lambda lat, lon, timeout=10.0: {
            "source": "synthetic-fallback",
            "live": False,
            "wind_kph": 20.0,
            "observed_at": None,
        },
    )
    monkeypatch.setattr(
        live_air,
        "fetch_air_traffic",
        lambda timeout=10.0, boxes=None, points=None: {
            "source": "synthetic-fallback",
            "live": False,
            "airborne_origin": None,
            "airborne_dest": None,
            "observed_at": None,
        },
    )
    monkeypatch.setattr(
        live_road,
        "fetch_corridor_congestion",
        lambda timeout=10.0, points=(), origin=(), dest=(): {
            "source": "synthetic-fallback",
            "live": False,
            "worst_ratio": None,
            "points": [],
            "incidents": None,
            "route": None,
            "observed_at": None,
        },
    )
    monkeypatch.setattr(
        live_rail,
        "fetch_entur_disruptions",
        lambda timeout=10.0, stop_id="x": {
            "source": "synthetic-fallback",
            "live": False,
            "active_count": None,
            "severe_count": None,
            "observed_at": None,
        },
    )
    monkeypatch.setattr(geo, "nearest_entur_stop", lambda lat, lon, timeout=10.0: None)


def test_haversine_matches_known_corridor():
    distance = geo.haversine_km(
        (ROTTERDAM["lat"], ROTTERDAM["lon"]), (OSLO["lat"], OSLO["lon"])
    )
    assert 900 < distance < 1100


def test_opensky_box_centers_on_point():
    assert geo.opensky_box(52.0, 4.0, half=0.4) == {
        "lamin": 51.6,
        "lomin": 3.6,
        "lamax": 52.4,
        "lomax": 4.4,
    }


def test_midpoint_averages_endpoints():
    assert geo.midpoint((0.0, 0.0), (10.0, 20.0)) == (5.0, 10.0)


def test_get_corridor_unknown_lists_known():
    with pytest.raises(ValueError, match="unknown corridor"):
        geo.get_corridor("atlantis")


def test_corridors_span_three_continents():
    lons = [
        endpoint["lon"]
        for corridor in geo.CORRIDORS.values()
        for endpoint in (corridor["origin"], corridor["dest"])
    ]
    assert any(lon < -50 for lon in lons)  # Americas
    assert any(lon > 50 for lon in lons)  # Asia
    assert any(-20 < lon < 40 for lon in lons)  # Europe/Africa
    assert len(geo.CORRIDORS) >= 5


def test_geocode_parses_first_result(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return httpx.Response(
            200,
            json=[{"lat": "53.55", "lon": "10.0", "display_name": "Hamburg"}],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    assert geo.geocode("Hamburg") == ("Hamburg", 53.55, 10.0)


def test_geocode_empty_raises(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return httpx.Response(
            200, json=[], request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(ValueError, match="not found"):
        geo.geocode("Atlantis")


def test_nearest_stop_picks_closest(monkeypatch):
    def fake_post(url, json=None, headers=None, timeout=None):
        return httpx.Response(
            200,
            json={
                "data": {
                    "matches": [
                        {
                            "id": "far",
                            "name": "Far",
                            "latitude": 59.0,
                            "longitude": 10.0,
                        },
                        {
                            "id": "near",
                            "name": "Near",
                            "latitude": 59.9,
                            "longitude": 10.75,
                        },
                    ]
                }
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    assert geo.nearest_entur_stop(59.91, 10.75) == ("near", "Near")


def test_nearest_stop_none_when_empty(monkeypatch):
    def fake_post(url, json=None, headers=None, timeout=None):
        return httpx.Response(
            200,
            json={"data": {"matches": []}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    assert geo.nearest_entur_stop(31.2, 121.4) is None


def test_snapshot_all_live_ranks_four(monkeypatch):
    _patch_live_layers(monkeypatch)
    snap = snapshot_mod.snapshot_for_corridor("north-sea")
    assert [o["mode"] for o in snap["ranked_options"]] != []
    assert len(snap["ranked_options"]) == 4
    assert [o["rank"] for o in snap["ranked_options"]] == [1, 2, 3, 4]
    assert all(o["score"] is not None for o in snap["ranked_options"])
    assert all(snap["legs"][mode]["live"] for mode in ("sea", "air", "road", "rail"))
    assert (
        snap["provenance"]["sea"]["delay_hours"] == "estimated-from-conditions"
    )
    assert snap["fastest_alternative"]["mode"] in ("sea", "air", "road", "rail")


def test_snapshot_storm_downgrades_sea(monkeypatch):
    _patch_live_layers(monkeypatch, wave=9.0, wind=110.0)
    snap = snapshot_mod.snapshot_for_corridor("north-sea")
    sea = next(o for o in snap["ranked_options"] if o["mode"] == "sea")
    assert snap["legs"]["sea"]["delay_hours"] == 48
    assert snap["legs"]["sea"]["status"] == "disrupted"
    assert sea["rank"] == 4
    assert snap["fastest_alternative"]["mode"] != "sea"


def test_snapshot_offline_keeps_four_defaults(monkeypatch):
    _patch_offline(monkeypatch)
    snap = snapshot_mod.snapshot_for_corridor("north-sea")
    assert len(snap["ranked_options"]) == 4
    for mode in ("sea", "air", "road", "rail"):
        leg = snap["legs"][mode]
        assert leg["live"] is False
        assert leg["delay_hours"] == snapshot_mod.DEFAULT_DELAY_HOURS
        assert snap["provenance"][mode]["delay_hours"] == "estimated-default"


def test_snapshot_transpacific_excludes_land_legs(monkeypatch):
    _patch_live_layers(monkeypatch)
    snap = snapshot_mod.snapshot_for_corridor("transpacific")
    assert {o["mode"] for o in snap["ranked_options"]} == {"sea", "air"}
    assert snap["legs"]["road"]["applicable"] is False
    assert snap["legs"]["rail"]["applicable"] is False
    assert snap["legs"]["road"]["reason"] != ""
    assert snap["fastest_alternative"]["mode"] in ("sea", "air")


def test_snapshot_custom_places(monkeypatch):
    _patch_live_layers(monkeypatch)
    monkeypatch.setattr(geo, "geocode", lambda name, timeout=10.0: (name, 50.0, 5.0))
    snap = snapshot_mod.snapshot_for_places("Alpha", "Beta")
    assert snap["label"] == "Alpha → Beta"
    assert len(snap["ranked_options"]) == 4


def test_endpoint_corridor(monkeypatch):
    _patch_live_layers(monkeypatch)
    body = world_snapshot(corridor="north-sea")
    assert len(body["ranked_options"]) == 4
    assert body["corridor"] == "north-sea"


def test_endpoint_unknown_corridor_is_400():
    with pytest.raises(Exception, match="unknown corridor"):
        world_snapshot(corridor="atlantis")


def test_lab_worldwide_section():
    from storm_lab import render_storm_lab

    html = render_storm_lab()
    for target in (
        "lab-corridor",
        "lab-from",
        "lab-to",
        "lab-snapshot-btn",
        "lab-snapshot-out",
        "/snapshot?corridor=",
        "labAskContext",
        "transpacific",
    ):
        assert target in html
    assert "innerHTML" not in html


def test_lab_ask_grounds_on_corridor():
    from storm_lab import render_storm_lab

    html = render_storm_lab()
    assert "labAskContext()" in html.rsplit("<script>", 1)[1]
    assert "&corridor=" in html
