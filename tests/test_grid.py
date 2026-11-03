"""Tests for the observable grid page (string checks, no browser)."""

from grid_page import render_grid_page

BANNED_WORDS = ["dashboard", "command center", "control tower"]


def test_page_calls_the_json_endpoints():
    html = render_grid_page()
    for path in (
        "/demo/north-sea-storm",
        "/demo/north-sea-storm/summary",
        "/demo/north-sea-storm/brief",
        "/demo/north-sea-storm/openweights",
        "/demo/north-sea-storm/openweights/ask",
    ):
        assert path in html
    assert "Live wind layer" not in html


def test_page_has_ranking_without_stage_tools():
    html = render_grid_page()
    assert "Ranked reroutes" in html
    for gone in (
        "What-if planner",
        "Run SAM verification",
        "Generate port image",
        "Route challenge",
    ):
        assert gone not in html
    assert "route briefing" in html.lower()


def test_page_has_optional_meta_models_section():
    html = render_grid_page()
    assert "AI analysis and evidence" in html
    assert "<details" in html
    assert "Explain this scenario" in html
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
        "/demo/north-sea-storm/openweights?model=",
        "/demo/north-sea-storm/openweights/ask?model=",
    ):
        assert script.count(path) == 1


def test_page_avoids_banned_framing_words():
    html = render_grid_page().lower()
    for word in BANNED_WORDS:
        assert word not in html


def test_ask_context_names_incident_default():
    html = render_grid_page()
    assert 'id="grid-ask-context"' in html
    assert "Asking about: North Sea incident" in html


def test_findings_render_as_labeled_mode_cards():
    html = render_grid_page()
    assert "Specialist findings" in html
    script = html.split("<script>", 1)[1]
    assert "mode-card" in script
    assert "layerInfo" in script
    for label in ("Live", "Estimated", "Unavailable"):
        assert label in script
    assert "updated " in script


def test_ranking_renders_as_cards_not_table():
    html = render_grid_page()
    assert "Ranked reroutes" in html
    assert 'id="ranking"' in html
    assert "<table" not in html
    script = html.split("<script>", 1)[1]
    assert "opt-card" in script
