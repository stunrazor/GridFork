"""Muse Image illustration: generated port/storm imagery for the demo.

This is illustrative image generation, separate from SAM 3.1 segmentation:
nothing here is measured or detected; the picture visualizes the scenario.

Documented values below come from the official Meta Model API docs
(https://dev.meta.ai/docs/image-generation):
- Endpoint ``POST https://api.meta.ai/v1/images/generations``
  (single-shot images endpoints, OpenAI Images API compatible)
- Model ``muse-image-1.0`` (Models page; request examples)
- Request ``{"model", "prompt", "n": 1}`` with
  ``Authorization: Bearer <key>`` (request examples)
- ``size`` is an optional ``"WxH"`` aspect-ratio hint; omit for default
- ``response_format`` ``"b64_json"`` (default) returns base64 bytes in
  ``data[].b64_json``; ``"url"`` returns a temporary signed URL instead
- ``output_format`` defaults to ``"webp"`` (``"png"``/``"jpeg"`` optional)

The API key is read from the ``META_MODEL_API_KEY`` environment variable and
is never logged or printed. Any failure (missing key, network error, bad
response) reports ``source: "unavailable"`` with no image bytes.
"""

import os

import httpx

# Documented endpoint and model identifier. Do not change without checking
# https://dev.meta.ai/docs/image-generation and https://dev.meta.ai/docs/models.
IMAGES_URL = "https://api.meta.ai/v1/images/generations"
MODEL_ID = "muse-image-1.0"
API_KEY_ENV_VAR = "META_MODEL_API_KEY"


def build_scenario_prompt(scenario_label: str, wave_height_m: float, wind_kph: float) -> str:
    """Build a deterministic illustration prompt grounded in the scenario."""
    return (
        "Illustration of a container port in a North Sea storm, "
        f"large waves about {wave_height_m} meters, gale wind about {wind_kph} kph, "
        "container ship waiting offshore, stacked containers on the quay. "
        f"Scene label: {scenario_label}."
    )


def fetch_generated_image(prompt: str, api_key: str, timeout: float = 120.0) -> dict:
    """Call the documented images endpoint; return format plus base64 bytes.

    Raises on transport errors, non-2xx status, or an unexpected payload.
    The key is sent only as a Bearer [REDACTED] never logged.
    """
    response = httpx.post(
        IMAGES_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL_ID,
            "prompt": prompt,
            "n": 1,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()["data"][0]
    return {"output_format": "webp", "b64_json": str(payload["b64_json"])}


def generate_scenario_image(
    scenario_label: str, wave_height_m: float, wind_kph: float
) -> dict:
    """Return an illustration dict, preferring Muse Image with an honest fallback.

    Offline the result carries no bytes: callers must render the ``note``
    instead of inventing a picture.
    """
    prompt = build_scenario_prompt(scenario_label, wave_height_m, wind_kph)
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        return {
            "source": "unavailable",
            "prompt": prompt,
            "data_url": None,
            "note": "Set META_MODEL_API_KEY and retry to generate the illustration.",
        }
    try:
        result = fetch_generated_image(prompt, api_key)
    except Exception:
        return {
            "source": "unavailable",
            "prompt": prompt,
            "data_url": None,
            "note": "Muse Image call failed; no illustration generated.",
        }
    return {
        "source": "muse-image",
        "prompt": prompt,
        "data_url": f"data:image/{result['output_format']};base64,{result['b64_json']}",
        "note": "AI-generated illustration, not a photograph or measurement.",
    }
