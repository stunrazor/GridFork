"""Tests for the observable grid page (string checks, no browser)."""

from grid_page import render_grid_page

BANNED_WORDS = ["dashboard", "command center", "control tower"]


def test_page_calls_the_json_endpoints():
    html = render_grid_page()
    for path in (
        "/demo/north-sea-storm",
        "/demo/north-sea-storm/summary",
        "/demo/north-sea-storm/vision",
        "/demo/north-sea-storm/weather",
        "/demo/north-sea-storm/brief",
        "/demo/north-sea-storm/image",
        "/demo/north-sea-storm/openweights",
        "/demo/north-sea-storm/openweights/ask",
    ):
        assert path in html


def test_page_has_ranking_and_vision_beats():
    html = render_grid_page()
    assert "Ranked reroutes" in html
    assert "Run SAM verification" in html
    assert "muse-spark" in html
    assert "sam-3.1" in html


def test_page_has_optional_meta_models_section():
    html = render_grid_page()
    assert "Meta Models (optional)" in html
    assert "Explain this scenario" in html
    assert "Generate port image" in html
    assert "Separate from SAM" in html
    assert "Check Spark Open runner" in html
    assert "Check Glimmer runner" in html
    assert "Classify with Spark Open" in html
    assert "Classify with Glimmer" in html
    assert "Nothing here runs on page load" in html


def test_meta_models_section_makes_no_onload_calls():
    html = render_grid_page()
    script = html.split("<script>", 1)[1]
    for path in (
        "/demo/north-sea-storm/brief",
        "/demo/north-sea-storm/image",
        "/demo/north-sea-storm/openweights?model=",
        "/demo/north-sea-storm/openweights/ask?model=",
    ):
        assert script.count(path) == 1


def test_page_avoids_banned_framing_words():
    html = render_grid_page().lower()
    for word in BANNED_WORDS:
        assert word not in html
