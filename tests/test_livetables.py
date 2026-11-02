"""Tests for one-click live tables (string checks, no browser).

Storm scenario stays the default render; one click re-renders the grid
findings/ranking and the routes hero/KPIs/comparison from /live.
"""

from grid_page import render_grid_page
from routes_page import render_routes_page
from orchestrator import run_demo


def test_grid_live_button_rerenders_tables():
    script = render_grid_page().split("<script>", 1)[1]
    assert "function renderDemo(demo)" in script
    assert "renderDemo(snap)" in script
    assert script.count("/demo/north-sea-storm/live") == 2


def test_grid_loads_live_on_open():
    html = render_grid_page()
    assert "Switch live/baseline tables" in html
    script = html.split("<script>", 1)[1]
    assert 'renderDemo(await getJSON("/demo/north-sea-storm/live"))' in script
    assert "let liveOn = true;" in script


def test_grid_live_button_toggles_back_to_storm():
    script = render_grid_page().split("<script>", 1)[1]
    assert "renderDemo(demo)" in script
    assert "liveOn" in script


def test_routes_live_values_button_updates_hero_kpis_table():
    html = render_routes_page(run_demo())
    assert "rt-live-values-btn" in html
    assert "rt-hero-title" in html
    assert "rt-comp-body" in html
    script = html.split("<script>", 1)[1]
    assert script.count("/demo/north-sea-storm/live") == 1
    for target in ("rt-hero-title", "rt-kpi-score", "rt-comp-body"):
        assert target in script
    assert 'id="rt-schem-sea-bar"' in html
    assert 'id="rt-schem-sea-text"' in html
    assert '"rt-schem-" + f.mode' in script


def test_routes_loads_live_values_on_open():
    html = render_routes_page(run_demo())
    assert "Refresh live values" in html
    assert "Loading live values" in html
    script = html.split("<script>", 1)[1]
    assert "async function rtLoadLiveValues()" in script
    assert "\nrtLoadLiveValues();" in script
    assert script.count("/demo/north-sea-storm/live") == 1
