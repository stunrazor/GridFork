"""Tests for the GridFork landing page (string checks, no browser)."""

from briefing_card import render_brief_card
from grid_page import render_grid_page
from landing_page import render_landing
from main import landing
from orchestrator import run_demo
from routes_page import render_routes_page
from storm_lab import render_storm_lab


def test_landing_is_deterministic():
    assert render_landing() == render_landing()


def test_landing_links_all_four_views():
    html = render_landing()
    assert "GridFork" in html
    for path in (
        "/demo/routes",
        "/demo/grid",
        "/demo/storm-lab",
        "/demo/north-sea-storm/brief-card",
    ):
        assert f'href="{path}"' in html
    assert "Route briefing" in html
    assert "Live grid" in html
    assert "Storm Scenario Lab" in html
    assert "Incident brief" in html


def test_landing_labels_synthetic_and_on_demand():
    lowered = render_landing().lower()
    assert "synthetic" in lowered
    assert "on demand" in lowered or "on-demand" in lowered


def test_landing_avoids_banned_framing_words():
    html = render_landing().lower()
    for word in ("dashboard", "command center", "control tower", "console"):
        assert word not in html


def test_root_endpoint_returns_landing():
    html = landing()
    assert "GridFork" in html
    assert 'href="/demo/routes"' in html


def test_every_view_links_home():
    assert 'href="/"' in render_grid_page()
    assert 'href="/"' in render_routes_page(run_demo())
    assert 'href="/"' in render_storm_lab()
    assert 'href="/"' in render_brief_card(run_demo())
