"""SAM 3.1 visual verification: segment prompted logistics objects in one image.

Documented values below come from the official Meta Model API docs
(https://dev.meta.ai/docs/):
- Endpoint ``POST https://api.meta.ai/v1/responses`` (SAM overview; Responses API)
- Model ``sam-3.1`` (Models page: text prompt, image, video in; boxes and masks out)
- Request ``{"model", "input": [message with input_text + input_image]}``
  with ``Authorization: Bearer <key>`` (Segmenting with prompts)
- ``input_text`` holds one short noun phrase naming one concept;
  ``input_image.image_url`` is a public URL or a base64 data URL
  (Segmenting with prompts: Build the request)
- Non-streaming (``stream`` omitted) runs the same segmentation and returns
  the complete result in one response, in the same format
  (Segmenting with prompts: Stream the response)
- Output text in ``output[].content[]`` parts with ``type == "output_text"``
  (Responses API example response); a single image yields one ``<0f>`` line
  with one record per match, each an object id plus one box token and one
  mask token (Reading segmentation output)
- Zero matches is valid: empty output text, not an error

SAM 3.1 returns geometry only (boxes and masks). It does not produce a
congestion score: ``congestion_score_from_counts`` is an explicit,
GridFork-side heuristic that converts detection counts to a 0..1 score, kept
as a separate testable function.

The API key is read from the ``META_MODEL_API_KEY`` environment variable
(GridFork convention, shared with spark_client; the docs call it
``MODEL_API_KEY``) and is never logged or printed. Without a key, or when the
API call fails, ``segment_image`` reports ``source: "unavailable"`` with no
detections rather than inventing geometry.
"""

import os
import re

import httpx

# Documented endpoint and model identifier. Do not change without checking
# https://dev.meta.ai/docs/sam/overview and https://dev.meta.ai/docs/models.
RESPONSES_URL = "https://api.meta.ai/v1/responses"
MODEL_ID = "sam-3.1"
API_KEY_ENV_VAR = "META_MODEL_API_KEY"

_LINE_RE = re.compile(r"<(\d+)f>(.+)")
_RECORD_SPLIT_RE = re.compile(r",(?=\d+<\|box;)")
_RECORD_RE = re.compile(r"(\d+)(<\|box;[^|]*\|>)(<\|mask;[^|]*\|>)")
_BOX_RE = re.compile(
    r"<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=(\d+);h=(\d+)"
    r"(?:;c=([0-9]+(?:\.[0-9]+)?))?\|>"
)
_MASK_RE = re.compile(
    r"<\|mask;x=0;y=0(?:;c=([0-9]+(?:\.[0-9]+)?))?;data=(\d+),(\d+),([~!])([^|]*)\|>"
)
_ENCODINGS = {"~": "lossless", "!": "one_bit"}


def build_segmentation_request(concept: str, image_url: str) -> dict:
    """Build the documented non-streaming request body for one image + concept."""
    if not isinstance(concept, str) or not concept.strip():
        raise ValueError("concept must be a non-empty noun phrase")
    if not isinstance(image_url, str) or not image_url.strip():
        raise ValueError("image_url must be a non-empty URL")
    return {
        "model": MODEL_ID,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": concept.strip()},
                    {"type": "input_image", "image_url": image_url.strip()},
                ],
            }
        ],
    }


def _parse_record(frame: int, record: str) -> dict:
    """Parse one documented record: object id + box token + mask token."""
    match = _RECORD_RE.fullmatch(record)
    if match is None:
        raise ValueError(f"malformed segmentation record: {record!r}")
    object_id, box_token, mask_token = match.groups()
    box = _BOX_RE.fullmatch(box_token)
    mask = _MASK_RE.fullmatch(mask_token)
    if box is None or mask is None:
        raise ValueError(f"malformed segmentation record: {record!r}")
    x1, y1, x2, y2, w, h, confidence = box.groups()
    _, mask_h, mask_w, encoding_marker, payload = mask.groups()
    detection = {
        "object_id": int(object_id),
        "frame": frame,
        "box": {
            "x1": int(x1), "y1": int(y1),
            "x2": int(x2), "y2": int(y2),
            "w": int(w), "h": int(h),
        },
        "mask": {
            "height": int(mask_h),
            "width": int(mask_w),
            "encoding": _ENCODINGS[encoding_marker],
            "payload": payload,
        },
    }
    if confidence is not None:
        detection["confidence"] = float(confidence)
    return detection


def parse_segmentation_output(output_text: str) -> list[dict]:
    """Parse documented output text into per-match detection dicts.

    Empty text is the documented zero-match result and yields ``[]``.
    """
    detections = []
    for line in output_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        match = _LINE_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"malformed segmentation line: {line!r}")
        frame = int(match.group(1))
        for record in _RECORD_SPLIT_RE.split(match.group(2)):
            detections.append(_parse_record(frame, record))
    return detections


def extract_output_text(payload: dict) -> str:
    """Read the output-text lane from a non-streaming Responses payload."""
    texts = []
    for item in payload["output"]:
        if item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if part.get("type") == "output_text":
                texts.append(part.get("text", ""))
    return "".join(texts)


def fetch_segmentation(
    concept: str, image_url: str, api_key: str, timeout: float = 30.0
) -> str:
    """Call the documented Responses endpoint and return the raw output text.

    Raises on transport errors, non-2xx status, or an unexpected payload.
    The key is sent only as a Bearer [REDACTED] never logged.
    """
    response = httpx.post(
        RESPONSES_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=build_segmentation_request(concept, image_url),
        timeout=timeout,
    )
    response.raise_for_status()
    return extract_output_text(response.json())


def _unavailable(concept: str) -> dict:
    return {
        "source": "unavailable",
        "concept": concept,
        "detections": [],
        "note": "no live SAM 3.1 verification ran (missing key or API error)",
    }


def segment_image(concept: str, image_url: str) -> dict:
    """Segment one concept in one image; unavailable offline or on API error."""
    request_body = build_segmentation_request(concept, image_url)
    concept = request_body["input"][0]["content"][0]["text"]
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        return _unavailable(concept)
    try:
        output_text = fetch_segmentation(concept, image_url, api_key)
        detections = parse_segmentation_output(output_text)
    except Exception:
        return _unavailable(concept)
    return {"source": "sam-3.1", "concept": concept, "detections": detections}


def congestion_score_from_counts(counts: dict, capacity: int = 10) -> float:
    """Convert per-concept detection counts to a 0..1 congestion score.

    This is a GridFork-side heuristic, NOT something SAM 3.1 produces: the
    model returns only boxes and masks. Total detections at or above
    ``capacity`` score 1.0; fewer scale linearly.
    """
    if not isinstance(capacity, int) or capacity <= 0:
        raise ValueError("capacity must be a positive integer")
    total = 0
    for label, count in counts.items():
        if not isinstance(count, int) or count < 0:
            raise ValueError(f"count for {label!r} must be a non-negative integer")
        total += count
    return round(min(1.0, total / capacity), 4)
