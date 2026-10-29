"""Tests for the SAM 3.1 visual-verification integration (fully mocked, no network).

No test here requires a real API key or network access: HTTP is stubbed and
META_MODEL_API_KEY is controlled via monkeypatch with a fake value.
"""

import httpx
import pytest

import sam_client

FAKE_KEY = "test-key-not-real"
CONCEPT = "delivery van"
IMAGE_URL = "https://example.com/yard.png"

# Wire examples shaped exactly like the documented grammar
# (https://dev.meta.ai/docs/sam/reading-segmentation).
ONE_MATCH = (
    "<0f>0<|box;x1=181;y1=365;x2=556;y2=486;w=1516;h=1600|>"
    "<|mask;x=0;y=0;data=122,376,~AB12cd34|>"
)
THREE_MATCHES = (
    "<0f>0<|box;x1=353;y1=382;x2=453;y2=427;w=537;h=561|>"
    "<|mask;x=0;y=0;data=46,101,~AA11|>,"
    "1<|box;x1=260;y1=382;x2=340;y2=427;w=537;h=561|>"
    "<|mask;x=0;y=0;data=46,81,~BB22|>,"
    "2<|box;x1=516;y1=117;x2=536;y2=150;w=537;h=561|>"
    "<|mask;x=0;y=0;data=34,21,~CC33|>"
)
SPARSE_IDS = (
    "<0f>0<|box;x1=10;y1=10;x2=20;y2=20;w=100;h=100|>"
    "<|mask;x=0;y=0;data=2,2,~AA|>,"
    "2<|box;x1=30;y1=30;x2=40;y2=40;w=100;h=100|>"
    "<|mask;x=0;y=0;data=2,2,~BB|>"
)
WITH_CONFIDENCE = (
    "<0f>1<|box;x1=444;y1=625;x2=679;y2=850;w=1800;h=1200;c=0.9609375|>"
    "<|mask;x=0;y=0;c=0.9609375;data=226,236,!DD44|>"
)


def _responses_payload(output_text):
    return {
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {"type": "output_text", "text": output_text, "annotations": []}
                ],
            }
        ]
    }


def _ok_response(output_text):
    return httpx.Response(
        200,
        json=_responses_payload(output_text),
        request=httpx.Request("POST", sam_client.RESPONSES_URL),
    )


def test_request_builder_uses_documented_shape():
    body = sam_client.build_segmentation_request(CONCEPT, IMAGE_URL)
    assert body == {
        "model": "sam-3.1",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": CONCEPT},
                    {"type": "input_image", "image_url": IMAGE_URL},
                ],
            }
        ],
    }


def test_request_builder_rejects_empty_concept_or_image():
    with pytest.raises(ValueError):
        sam_client.build_segmentation_request("  ", IMAGE_URL)
    with pytest.raises(ValueError):
        sam_client.build_segmentation_request(CONCEPT, "")


def test_parse_single_match_returns_documented_evidence():
    (detection,) = sam_client.parse_segmentation_output(ONE_MATCH)
    assert detection["object_id"] == 0
    assert detection["frame"] == 0
    assert detection["box"] == {
        "x1": 181, "y1": 365, "x2": 556, "y2": 486, "w": 1516, "h": 1600,
    }
    assert detection["mask"] == {
        "height": 122, "width": 376, "encoding": "lossless", "payload": "AB12cd34",
    }
    assert "confidence" not in detection


def test_parse_multiple_matches_keeps_each_box_with_its_mask():
    detections = sam_client.parse_segmentation_output(THREE_MATCHES)
    assert [d["object_id"] for d in detections] == [0, 1, 2]
    assert detections[1]["box"]["x1"] == 260
    assert detections[1]["mask"] == {
        "height": 46, "width": 81, "encoding": "lossless", "payload": "BB22",
    }
    assert detections[2]["box"] == {
        "x1": 516, "y1": 117, "x2": 536, "y2": 150, "w": 537, "h": 561,
    }


def test_parse_keeps_sparse_object_ids():
    detections = sam_client.parse_segmentation_output(SPARSE_IDS)
    assert [d["object_id"] for d in detections] == [0, 2]


def test_parse_reads_confidence_and_one_bit_encoding():
    (detection,) = sam_client.parse_segmentation_output(WITH_CONFIDENCE)
    assert detection["object_id"] == 1
    assert detection["confidence"] == pytest.approx(0.9609375)
    assert detection["mask"]["encoding"] == "one_bit"
    assert detection["mask"]["height"] == 226
    assert detection["mask"]["width"] == 236


def test_parse_empty_output_is_zero_matches_not_an_error():
    assert sam_client.parse_segmentation_output("") == []
    assert sam_client.parse_segmentation_output("  \n ") == []


def test_parse_malformed_line_raises():
    with pytest.raises(ValueError):
        sam_client.parse_segmentation_output("not a segmentation line")


def test_fetch_uses_documented_endpoint_model_and_format(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _ok_response(ONE_MATCH)

    monkeypatch.setattr(sam_client.httpx, "post", fake_post)
    assert sam_client.fetch_segmentation(CONCEPT, IMAGE_URL, FAKE_KEY) == ONE_MATCH
    assert captured["url"] == "https://api.meta.ai/v1/responses"
    assert captured["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["json"]["model"] == "sam-3.1"
    assert captured["json"]["input"][0]["content"] == [
        {"type": "input_text", "text": CONCEPT},
        {"type": "input_image", "image_url": IMAGE_URL},
    ]


def test_fetch_empty_output_text_is_zero_matches(monkeypatch):
    monkeypatch.setattr(
        sam_client.httpx, "post", lambda *a, **k: _ok_response("")
    )
    assert sam_client.fetch_segmentation(CONCEPT, IMAGE_URL, FAKE_KEY) == ""


def test_segment_image_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)

    def fail_post(*args, **kwargs):
        raise AssertionError("must not call network without a key")

    monkeypatch.setattr(sam_client.httpx, "post", fail_post)
    result = sam_client.segment_image(CONCEPT, IMAGE_URL)
    assert result["source"] == "unavailable"
    assert result["concept"] == CONCEPT
    assert result["detections"] == []


def test_segment_image_unavailable_on_api_error(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)

    def error_post(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(sam_client.httpx, "post", error_post)
    result = sam_client.segment_image(CONCEPT, IMAGE_URL)
    assert result["source"] == "unavailable"
    assert result["detections"] == []


def test_segment_image_returns_evidence_on_success(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)
    monkeypatch.setattr(
        sam_client.httpx, "post", lambda *a, **k: _ok_response(THREE_MATCHES)
    )
    result = sam_client.segment_image(CONCEPT, IMAGE_URL)
    assert result["source"] == "sam-3.1"
    assert result["concept"] == CONCEPT
    assert [d["object_id"] for d in result["detections"]] == [0, 1, 2]


def test_segment_image_rejects_empty_concept_without_network(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    with pytest.raises(ValueError):
        sam_client.segment_image(" ", IMAGE_URL)


def test_congestion_score_scales_with_total_count():
    assert sam_client.congestion_score_from_counts({}) == 0.0
    assert sam_client.congestion_score_from_counts({"delivery van": 0}) == 0.0
    assert sam_client.congestion_score_from_counts({"delivery van": 5}) == 0.5
    assert sam_client.congestion_score_from_counts({"delivery van": 10}) == 1.0


def test_congestion_score_caps_above_capacity_and_sums_concepts():
    assert sam_client.congestion_score_from_counts({"delivery van": 99}) == 1.0
    assert (
        sam_client.congestion_score_from_counts(
            {"delivery van": 3, "container": 4}, capacity=14
        )
        == 0.5
    )


def test_congestion_score_rejects_bad_inputs():
    with pytest.raises(ValueError):
        sam_client.congestion_score_from_counts({"delivery van": -1})
    with pytest.raises(ValueError):
        sam_client.congestion_score_from_counts({"delivery van": 2}, capacity=0)
