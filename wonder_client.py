"""Muse Wonder deep analysis: structured cascade brief for the demo.

Documented values below come from the official Meta Model API docs
(https://dev.meta.ai/docs/):
- Base URL ``https://api.meta.ai/v1`` (API reference)
- Model ``muse-wonder-1.0`` (Models page: agentic work, coding, reasoning)
- Chat Completions protocol supported for Wonder (Models page)
- Request ``{"model", "messages": [{"role", "content"}]}`` with
  ``Authorization: Bearer <key>`` (Create a chat completion)
- Response text at ``choices[0].message.content`` (schemas + SDK examples)

The API key is read from the ``META_MODEL_API_KEY`` environment variable and
is never logged or printed. Any failure (missing key, network error, bad
response) falls back to the deterministic brief so the demo keeps working
offline.
"""

import os

import httpx

# Documented endpoint and model identifier. Do not change without checking
# https://dev.meta.ai/docs/models and https://dev.meta.ai/docs/api-reference.
CHAT_COMPLETIONS_URL = "https://api.meta.ai/v1/chat/completions"
MODEL_ID = "muse-wonder-1.0"
API_KEY_ENV_VAR = "META_MODEL_API_KEY"


def build_brief_prompt(ranked_options: list[dict], findings: list[dict]) -> str:
    """Build a deterministic prompt describing impacts and the ranking."""
    lines = [
        "Write a four-line cascade brief with exactly these labels, one per line:",
        "IMPACTS | RECOMMENDED_REROUTE | TRADEOFFS | CONFIDENCE.",
        "Synthetic demo data. Findings:",
    ]
    for finding in findings:
        lines.append(
            f"- {finding['mode']}: {finding['status']}, "
            f"+{finding['delay_hours']}h delay, "
            f"on-time {finding['on_time_probability']}."
        )
    lines.append("Ranking:")
    for option in ranked_options:
        lines.append(
            f"Rank {option['rank']}: {option['option_id']} "
            f"({option['title']}), score {option['score']}, "
            f"cost ${option['cost_usd']}, "
            f"saves {option['time_saved_hours']}h, "
            f"on-time {option['on_time_probability']}, "
            f"confidence {option['confidence']}."
        )
    return "\n".join(lines)


def deterministic_brief(ranked_options: list[dict], findings: list[dict]) -> str:
    """Deterministic fallback brief used when Muse Wonder is unavailable."""
    top = ranked_options[0]
    runner_up = ranked_options[1]
    impacted = [
        f"{f['mode']} {f['status']} (+{f['delay_hours']}h)"
        for f in findings
        if f["status"] != "available"
    ]
    cost_gap = runner_up["cost_usd"] - top["cost_usd"]
    time_gap = top["time_saved_hours"] - runner_up["time_saved_hours"]
    cost_word = f"saves ${cost_gap}" if cost_gap >= 0 else f"costs ${-cost_gap} more"
    time_word = f"saves {time_gap}h more" if time_gap >= 0 else f"saves {-time_gap}h less"
    return (
        f"IMPACTS: {', '.join(impacted)}. "
        f"RECOMMENDED_REROUTE: {top['option_id']} ({top['title']}). "
        f"TRADEOFFS: vs {runner_up['option_id']}, top pick {cost_word} "
        f"and {time_word}. "
        f"CONFIDENCE: {top['confidence']}."
    )


def fetch_wonder_brief(prompt: str, api_key: str, timeout: float = 60.0) -> str:
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


def generate_brief(ranked_options: list[dict], findings: list[dict]) -> dict:
    """Return a brief dict, preferring Muse Wonder with deterministic fallback."""
    prompt = build_brief_prompt(ranked_options, findings)
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        return {
            "source": "deterministic",
            "text": deterministic_brief(ranked_options, findings),
        }
    try:
        text = fetch_wonder_brief(prompt, api_key)
    except Exception:
        return {
            "source": "deterministic",
            "text": deterministic_brief(ranked_options, findings),
        }
    return {"source": "muse-wonder", "text": text}
