"""Tests for SAM visual ground truth wired into the demo (fully mocked).

No test here requires a real API key or network access: sam_client.segment_image
is stubbed and META_MODEL_API_KEY is controlled via monkeypatch.
"""

import orchestrator
import sam_client
from main import north_sea_storm_vision

LIVE_RESULT = {"source": "sam-3.1", "concept": "container", "detections": [{"object_id": i} for i in range(7)]}
UNAVAILABLE_RESULT = {"source": "unavailable", "concept": "container", "detections": [], "note": "no live SAM 3.1 verification ran"}


def _live_segment_image(concept, image_url):
    assert concept == "container"
    assert image_url.startswith("https://")
    return dict(LIVE_RESULT)


def _unavailable_segment_image(concept, image_url):
    return dict(UNAVAILABLE_RESULT)


def test_vision_block_reports_live_detections_and_score(monkeypatch):
    monkeypatch.setattr(sam_client, "segment_image", _live_segment_image)
    body = orchestrator.run_demo_with_vision()
    assert body["vision"]["source"] == "sam-3.1"
    assert body["vision"]["detections"] == 7
    assert body["vision"]["score"] == 0.7
    assert body["vision"]["concept"] == "container"


def test_live_vision_moves_sea_numbers(monkeypatch):
    monkeypatch.setattr(sam_client, "segment_image", _live_segment_image)
    plain = orchestrator.run_demo()["ranked_options"]
    vision = orchestrator.run_demo_with_vision()["ranked_options"]
    plain_sea = next(o for o in plain if o["option_id"] == "sea-wait")
    vision_sea = next(o for o in vision if o["option_id"] == "sea-wait")
    # 7 detections -> score 0.7 -> +8h port congestion on the sea leg.
    assert vision_sea["time_saved_hours"] == plain_sea["time_saved_hours"] - 8
    # Sea is already last, so the visible move is the widening leader margin.
    assert vision[0]["score"] - vision_sea["score"] > plain[0]["score"] - plain_sea["score"]


def test_unavailable_vision_leaves_ranking_unchanged(monkeypatch):
    monkeypatch.setattr(sam_client, "segment_image", _unavailable_segment_image)
    assert orchestrator.run_demo_with_vision()["ranked_options"] == orchestrator.run_demo()["ranked_options"]
    assert orchestrator.run_demo_with_vision()["vision"]["source"] == "unavailable"


def test_vision_falls_back_without_key(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    body = orchestrator.run_demo_with_vision()
    assert body["vision"]["source"] == "unavailable"
    assert body["ranked_options"] == orchestrator.run_demo()["ranked_options"]


def test_vision_endpoint_function_returns_demo_shape(monkeypatch):
    monkeypatch.setattr(sam_client, "segment_image", _live_segment_image)
    body = north_sea_storm_vision()
    assert body["synthetic"] is True
    assert len(body["findings"]) == 4
    assert len(body["ranked_options"]) == 4
    assert body["vision"]["source"] == "sam-3.1"
