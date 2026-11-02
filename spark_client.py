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
        "Summarize this North Sea storm freight reroute ranking in three sentences.",
        "State the top option, one key tradeoff vs the runner-up, and confidence.",
        "Synthetic demo data:",
    ]
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


def deterministic_summary(ranked_options: list[dict]) -> str:
    """Deterministic fallback summary used when Muse Spark is unavailable."""
    top = ranked_options[0]
    order = ", ".join(o["option_id"] for o in ranked_options)
    runner_up = ranked_options[1]
    cost_gap = runner_up["cost_usd"] - top["cost_usd"]
    time_gap = top["time_saved_hours"] - runner_up["time_saved_hours"]
    cost_word = f"saves ${cost_gap}" if cost_gap >= 0 else f"costs ${-cost_gap} more"
    time_word = f"saves {time_gap}h more" if time_gap >= 0 else f"saves {-time_gap}h less"
    return (
        f"Top recommendation is {top['option_id']} ({top['title']}) "
        f"with score {top['score']}. "
        f"Tradeoff vs {runner_up['option_id']}: top pick {cost_word} and {time_word}. "
        f"Full ranking: {order}."
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


def build_ask_prompt(
    question: str,
    findings: list[dict],
    ranked_options: list[dict],
    live: dict | None = None,
) -> str:
    """Build a grounded Q&A prompt over the ranking and findings.

    The model answers only from the data below; anything else — other
    incidents, live prices, advice beyond this ranking — is out of scope.
    When ``live`` carries the snapshot readouts, measured conditions and
    per-mode provenance join the prompt so traffic and disruption
    questions get measured answers.
    """
    lines = [
        "Answer the question below about this North Sea storm freight reroute.",
        "Use ONLY the ranking and findings given; answer in at most four sentences.",
        "If the question needs data not present here, or is not about this",
        'incident and ranking, start the answer with "Out of scope:" and say why.',
        "",
    ]
    lines.extend(build_ask_context(findings, ranked_options, live))
    lines.append(f"Question: {question}")
    return "\n".join(lines)


def build_ask_context(
    findings: list[dict], ranked_options: list[dict], live: dict | None = None
) -> list[str]:
    """Shared grounding block: ranking, findings, and live conditions."""
    lines = ["Ranking:"]
    for option in ranked_options:
        lines.append(
            f"Rank {option['rank']}: {option['option_id']} "
            f"({option['title']}), score {option['score']}, "
            f"cost ${option['cost_usd']}, "
            f"saves {option['time_saved_hours']}h, "
            f"on-time {option['on_time_probability']}, "
            f"confidence {option['confidence']}."
        )
    lines.append("Findings:")
    for finding in findings:
        lines.append(
            f"{finding['mode']}: {finding['status']}, "
            f"+{finding['delay_hours']}h delay, cost ${finding['cost_usd']}, "
            f"on-time {finding['on_time_probability']}. {finding['summary']}"
        )
    if live:
        lines.append("Live conditions (measured now, with sources):")
        lines.extend(_live_condition_lines(live))
    return lines


def _live_condition_lines(live: dict) -> list[str]:
    """Compact measured-condition lines plus delay provenance per mode."""
    marine = live.get("marine") or {}
    wind = live.get("wind") or {}
    air = live.get("air") or {}
    road = live.get("road") or {}
    rail = live.get("rail") or {}
    first = air.get("airborne_ams", air.get("airborne_origin"))
    second = air.get("airborne_osl", air.get("airborne_dest"))
    lines = [
        f"sea: {marine.get('wave_height_m')}m waves [{marine.get('source')}], "
        f"{wind.get('wind_kph')}kph wind [{wind.get('source')}].",
        f"air: {first}+{second} airborne "
        f"[endpoints, {air.get('source')}].",
    ]
    incidents = road.get("incidents") or {}
    route = road.get("route") or {}
    lines.append(
        f"road: worst flow ratio {road.get('worst_ratio')}, "
        f"{incidents.get('count')} incidents "
        f"({incidents.get('closures')} closures), routed "
        f"{route.get('transit_hours')}h [{road.get('source')}]."
    )
    lines.append(
        f"rail: {rail.get('active_count')} active, "
        f"{rail.get('severe_count')} severe [{rail.get('source')}]."
    )
    provenance = live.get("provenance", {})
    delays = ", ".join(
        f"{mode}={provenance.get(mode, {}).get('delay_hours')}"
        for mode in ("sea", "air", "road", "rail")
    )
    lines.append(f"Delay provenance: {delays}.")
    return lines


def answer_question(
    question: str,
    findings: list[dict],
    ranked_options: list[dict],
    live: dict | None = None,
) -> dict:
    """Answer one question via Muse Spark, or report setup/unavailable."""
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        return {
            "source": "setup-required",
            "model": MODEL_ID,
            "text": None,
            "detail": (
                f"No API key: set {API_KEY_ENV_VAR} to ask {MODEL_ID}."
            ),
        }
    try:
        text = fetch_spark_summary(
            build_ask_prompt(question, findings, ranked_options, live=live), api_key
        )
    except Exception:
        return {
            "source": "unavailable",
            "model": MODEL_ID,
            "text": None,
            "detail": "Muse Spark call failed; no answer produced.",
        }
    return {"source": "muse-spark", "model": MODEL_ID, "text": text}


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
