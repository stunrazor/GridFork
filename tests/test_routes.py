"""Tests for the route briefing page (string checks, no browser)."""

from grid_page import render_grid_page
from main import north_sea_storm_routes
from orchestrator import run_demo
from routes_page import render_routes_page


def _page():
    return render_routes_page(run_demo())


def test_page_is_deterministic():
    assert _page() == _page()


def test_hero_recommends_top_route_with_all_five_numbers():
    html = _page()
    assert "route briefing" in html.lower()
    assert "rail-reroute" in html
    assert "0.7988" in html
    assert "3800" in html
    assert "42h" in html
    assert "0.7" in html
    assert "0.72" in html


def test_kpi_strip_and_schematic_are_data_driven_and_labeled():
    html = _page()
    assert "kpi" in html.lower()
    assert "<svg" in html
    assert "not a map" in html.lower()
    for mode in ("sea", "air", "road", "rail"):
        assert mode in html


def test_side_brief_is_deterministic_with_no_live_call():
    html = _page()
    assert "operations brief" in html.lower()
    assert "Top recommendation is rail-reroute" in html
    assert "Refresh live" in html


def test_evidence_panels_cover_all_four_stages():
    html = _page()
    for head in ("Evidence", "What-if", "Model Bench", "Visual Brief"):
        assert head in html
    assert "Run SAM check" in html
    assert "Run scenario" in html
    assert "Hold to talk" in html
    assert "Run live comparison" in html
    assert "Preview with mock data" in html
    assert "Generate illustration" in html


def test_every_live_call_is_click_gated():
    html = _page()
    script = html.split("<script>", 1)[1]
    for path in (
        "/demo/north-sea-storm/vision",
        "/demo/north-sea-storm/whatif?q=",
        "/demo/north-sea-storm/transcribe",
        "/demo/north-sea-storm/challenge?models=",
        "/demo/north-sea-storm/image",
        "/demo/north-sea-storm/summary",
    ):
        assert script.count(path) == 1
    assert script.count("getUserMedia") == 1
    assert "addEventListener" in script


def test_badges_and_honest_labels():
    html = _page()
    lowered = html.lower()
    assert "synthetic demo data" in lowered
    assert "advisory" in lowered
    assert "illustrative" in lowered
    assert "deterministic" in lowered


def test_page_avoids_banned_framing_words():
    html = _page().lower()
    for word in ("dashboard", "command center", "control tower", "console"):
        assert word not in html


def test_endpoint_returns_routes_page():
    html = north_sea_storm_routes()
    assert "route briefing" in html.lower()
    assert "rail-reroute" in html


def test_grid_page_links_to_routes():
    assert 'href="/demo/routes"' in render_grid_page()
