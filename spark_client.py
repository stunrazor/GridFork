"""First Muse Spark integration: AI narrative summary for the North Sea demo.

Documented values below come from the official Meta Model API docs
(https://dev.meta.ai/docs/):
- Base URL ``https://api.meta.ai/v1`` (API reference)
- Endpoint ``POST /v1/chat/completions`` (API reference)
- Model ``muse-spark-1.3`` (Models page: latest, "Recommended for new work")
- Request ``{"model", "messages": [{"role", "content"}]}`` with
  ``Authorization: Bearer <key>`` (Create a chat completion)
- Response text at ``choices[0].message.content`` (schemas + SDK examples)

The API key is read from the ``META_MODEL_API_KEY`` environment variable and
is never logged or printed. Any failure (missing key, network error, bad
response) falls back to the deterministic template so the demo keeps working
offline.
"""

import os

import httpx

# Documented endpoint and model identifier. Do not change without checking
# https://dev.meta.ai/docs/api-reference and https://dev.meta.ai/docs/models.
CHAT_COMPLETIONS_URL = "https://api.meta.ai/v1/chat/completions"
MODEL_ID = "muse-spark-1.3"
API_KEY_ENV_VAR = "META_MODEL_API_KEY"


def build_summary_prompt(ranked_options: list[dict]) -> str:
    """Build a deterministic prompt describing the ranked reroute options."""
    lines = [
        "Summarize this North Sea storm freight reroute ranking in two sentences.",
        "State the top option and one key tradeoff. Synthetic demo data:",
    ]
    for option in ranked_options:
        lines.append(
            f"Rank {option['rank']}: {option['option_id']} "
            f"({option['title']}), score {option['score']}, "
            f"cost ${option['cost_usd']}, "
            f"saves {option['time_saved_hours']}h."
        )
    return "\n".join(lines)


def deterministic_summary(ranked_options: list[dict]) -> str:
    """Deterministic fallback summary used when Muse Spark is unavailable."""
    top = ranked_options[0]
    order = ", ".join(o["option_id"] for o in ranked_options)
    return (
        f"Top recommendation is {top['option_id']} ({top['title']}) "
        f"with score {top['score']}. Full ranking: {order}."
    )


def fetch_spark_summary(prompt: str, api_key: str, timeout: float = 30.0) -> str:
    """Call the documented chat-completions endpoint and return the text.

    Raises on transport errors, non-2xx status, or an unexpected payload.
    The key is sent only as a Bearer [REDACTED] never logged.
    """
    response = httpx.post(
        CHAT_COMPLETIONS_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return str(response.json()["choices"][0]["message"]["content"])


def generate_summary(ranked_options: list[dict]) -> dict:
    """Return a summary dict, preferring Muse Spark with deterministic fallback."""
    prompt = build_summary_prompt(ranked_options)
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        return {"source": "deterministic", "text": deterministic_summary(ranked_options)}
    try:
        text = fetch_spark_summary(prompt, api_key)
    except Exception:
        return {"source": "deterministic", "text": deterministic_summary(ranked_options)}
    return {"source": "muse-spark", "text": text}
