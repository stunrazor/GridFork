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
    assert script.count("/demo/north-sea-storm/live") == 1


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
    assert "Schematic stays storm-scenario" in script
