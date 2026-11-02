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

import json
import os
import re

import httpx

import spark_client

# Documented endpoint and model identifier. Do not change without checking
# https://dev.meta.ai/docs/models and https://dev.meta.ai/docs/api-reference.
CHAT_COMPLETIONS_URL = "https://api.meta.ai/v1/chat/completions"
MODEL_ID = "muse-wonder-1.0"
API_KEY_ENV_VAR = "META_MODEL_API_KEY"

# What-if assumption vocabulary. Deltas are added to the current scenario
# value by the deterministic engine; the model never scores or ranks.
WHATIF_MODES = ("sea", "air", "road", "rail")
WHATIF_FIELDS = ("delay_hours", "cost_usd", "on_time_probability", "confidence")

MODE_KEYWORDS = {
    "sea": ("sea", "rotterdam", "port", "ship", "vessel", "sail", "sailing", "storm"),
    "air": ("air", "flight", "fly", "ams", "schiphol", "plane", "de-icing", "deicing"),
    "road": ("road", "truck", "bridge", "denmark", "danish", "driver", "belt"),
    "rail": ("rail", "train", "intermodal", "corridor", "slot"),
}

NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}

_NUM_ALTERNATION = "|".join(
    sorted(NUMBER_WORDS, key=len, reverse=True) + [r"\d+"]
)
_HOUR_RE = re.compile(
    rf"\b(?P<num>{_NUM_ALTERNATION})\s*-?\s*"
    r"(?:more\s+|additional\s+|extra\s+)?(?P<unit>hours?|hrs?|h)\b"
)
_COST_RE = re.compile(
    r"\$\s*(?P<dollars>\d[\d,]*)|(?P<words>\d[\d,]*)\s*(?:dollars?|usd)\b",
    re.IGNORECASE,
)
# Words near an amount that flip its sign ("clears 10 hours early" -> -10).
_REDUCTION_CUES = (
    "less",
    "fewer",
    "shorter",
    "earlier",
    "early",
    "reduce",
    "reduced",
    "reduction",
    "cut",
    "save",
    "saves",
    "saved",
    "saving",
    "shave",
    "clear",
    "clears",
    "cleared",
    "ease",
    "eased",
    "cheaper",
    "discount",
)
_ALL_MODES_PHRASES = (
    "everything",
    "all modes",
    "every mode",
    "all routes",
    "every route",
    "all four",
)


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


def fetch_wonder_text(prompt: str, api_key: str, timeout: float = 60.0) -> str:
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


def fetch_wonder_brief(prompt: str, api_key: str, timeout: float = 60.0) -> str:
    """Fetch a cascade brief; kept as the stable name used by callers."""
    return fetch_wonder_text(prompt, api_key, timeout=timeout)


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


def build_whatif_prompt(
    question: str, ranked_options: list[dict], findings: list[dict]
) -> str:
    """Build a deterministic prompt asking Wonder for strict-JSON assumptions."""
    lines = [
        "Translate a freight what-if question into explicit scenario assumptions.",
        "Output ONLY strict JSON, no markdown, no commentary:",
        '{"assumptions": [{"mode": ..., "field": ..., "delta": ..., "reason": ...}],'
        ' "explanation": "..."}',
        'Allowed "mode": "sea", "air", "road", "rail.',
        'Allowed "field": "delay_hours" (integer hours), "cost_usd" (integer dollars),'
        ' "on_time_probability" (float change), "confidence" (float change).',
        '"delta" is ADDED to the current value. "reason" is one short phrase.',
        '"explanation" is one or two sentences for the operator.',
        "Rules: only include assumptions the question directly implies;",
        "extra closure or waiting hours become a positive delay_hours delta;",
        "use an empty assumptions array when nothing is quantifiable;",
        "never invent scores or rankings; a separate engine recomputes those.",
        "Synthetic demo data. Findings:",
    ]
    for finding in findings:
        lines.append(
            f"- {finding['mode']}: {finding['status']}, "
            f"+{finding['delay_hours']}h delay, "
            f"cost ${finding['cost_usd']}, "
            f"on-time {finding['on_time_probability']}."
        )
    lines.append("Current ranking:")
    for option in ranked_options:
        lines.append(
            f"Rank {option['rank']}: {option['option_id']}, "
            f"score {option['score']}."
        )
    lines.append(f"Question: {question.strip()}")
    return "\n".join(lines)


def build_wonder_ask_prompt(
    question: str,
    findings: list[dict],
    ranked_options: list[dict],
    live: dict | None = None,
) -> str:
    """Build an explanation-style Q&A prompt over the same grounding data."""
    lines = [
        "Explain the answer to the question below about this North Sea storm",
        "freight reroute: say what follows from the data and why, in at most",
        "four sentences. Reason only from the ranking and findings given;",
        "if the question needs data not present here, or is not about this",
        'incident and ranking, start the answer with "Out of scope:" and say why.',
        "",
    ]
    lines.extend(spark_client.build_ask_context(findings, ranked_options, live))
    lines.append(f"Question: {question}")
    return "\n".join(lines)


def answer_ask(
    question: str,
    findings: list[dict],
    ranked_options: list[dict],
    live: dict | None = None,
) -> dict:
    """Answer one question via Muse Wonder, or report setup/unavailable."""
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
        text = fetch_wonder_text(
            build_wonder_ask_prompt(question, findings, ranked_options, live=live),
            api_key,
        )
    except Exception:
        return {
            "source": "unavailable",
            "model": MODEL_ID,
            "text": None,
            "detail": "Muse Wonder call failed; no answer produced.",
        }
    return {"source": "muse-wonder", "model": MODEL_ID, "text": text}


def parse_whatif_response(text: str) -> dict:
    """Parse Wonder's strict-JSON what-if reply into assumptions + explanation.

    Raises ValueError when the reply is not usable JSON; individual
    assumption entries with an unknown mode, field, or non-numeric delta
    are dropped instead of failing the whole reply.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        fence_lines = cleaned.splitlines()[1:]
        if fence_lines and fence_lines[-1].strip().startswith("```"):
            fence_lines = fence_lines[:-1]
        cleaned = "\n".join(fence_lines).strip()
    try:
        payload = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"what-if reply is not JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("what-if reply must be a JSON object")
    raw_assumptions = payload.get("assumptions", [])
    if not isinstance(raw_assumptions, list):
        raise ValueError("what-if reply 'assumptions' must be a list")
    assumptions = []
    for item in raw_assumptions:
        if not isinstance(item, dict):
            continue
        mode, field, delta = item.get("mode"), item.get("field"), item.get("delta")
        if mode not in WHATIF_MODES or field not in WHATIF_FIELDS:
            continue
        if isinstance(delta, bool) or not isinstance(delta, (int, float)):
            continue
        if field in ("delay_hours", "cost_usd"):
            delta = int(round(delta))
        else:
            delta = round(float(delta), 4)
        reason = item.get("reason", "")
        assumptions.append(
            {
                "mode": mode,
                "field": field,
                "delta": delta,
                "reason": str(reason)[:200] if reason else "",
            }
        )
    explanation = payload.get("explanation", "")
    explanation = str(explanation).strip() if explanation else ""
    if not explanation:
        explanation = (
            "Muse Wonder provided scenario assumptions; "
            "the deterministic engine recomputed the ranking."
        )
    return {"assumptions": assumptions, "explanation": explanation}


def _keyword_positions(question: str) -> list[tuple[int, str]]:
    """Return (char position, mode) for every mode keyword in the question.

    Keywords match at a word start so plurals ("trucks") still hit while
    "air" inside "rail" does not.
    """
    positions = []
    for mode in WHATIF_MODES:
        for keyword in MODE_KEYWORDS[mode]:
            for match in re.finditer(r"\b" + re.escape(keyword), question):
                positions.append((match.start(), mode))
    return positions


def _nearest_modes(question: str, match_pos: int) -> list[str]:
    """Return the mode(s) an amount at match_pos applies to, if identifiable."""
    positions = _keyword_positions(question)
    if not positions:
        if any(phrase in question for phrase in _ALL_MODES_PHRASES):
            return list(WHATIF_MODES)
        return []
    best = min(abs(pos - match_pos) for pos, _ in positions)
    for pos, mode in sorted(positions):
        if abs(pos - match_pos) == best:
            return [mode]
    return []  # unreachable, kept for clarity


def _is_reduction(question: str, match_start: int) -> bool:
    """Check the words just before an amount for a reduction cue."""
    window = question[max(0, match_start - 30) : match_start]
    return any(cue in window for cue in _REDUCTION_CUES)


def _format_whatif_delta(mode: str, field: str, delta: int) -> str:
    if field == "delay_hours":
        return f"{mode} delay {delta:+d}h"
    if field == "cost_usd":
        return f"{mode} cost {delta:+d} USD"
    return f"{mode} {field} {delta:+d}"


def deterministic_whatif(question: str) -> dict:
    """Parse hour/cost amounts into assumptions without calling Wonder.

    Each amount attaches to the nearest mode keyword ("Rotterdam" implies
    the sea leg); amounts with no identifiable mode are skipped.
    """
    lowered = question.strip().lower()
    grouped: dict[tuple[str, str], list] = {}

    def add(mode: str, field: str, delta: int, span: str) -> None:
        key = (mode, field)
        if key in grouped:
            grouped[key][0] += delta
        else:
            grouped[key] = [delta, span.strip()[:60]]

    found_amount = False
    for match in _HOUR_RE.finditer(lowered):
        found_amount = True
        raw_num = match.group("num")
        hours = int(raw_num) if raw_num.isdigit() else NUMBER_WORDS.get(raw_num, 0)
        if hours == 0:
            continue
        if _is_reduction(lowered, match.start()):
            hours = -hours
        for mode in _nearest_modes(lowered, match.start()):
            add(mode, "delay_hours", hours, match.group(0))
    for match in _COST_RE.finditer(lowered):
        found_amount = True
        raw_amt = (match.group("dollars") or match.group("words") or "").replace(",", "")
        if not raw_amt.isdigit():
            continue
        dollars = int(raw_amt)
        if _is_reduction(lowered, match.start()):
            dollars = -dollars
        for mode in _nearest_modes(lowered, match.start()):
            add(mode, "cost_usd", dollars, match.group(0))

    assumptions = [
        {"mode": mode, "field": field, "delta": delta, "reason": f"Parsed '{span}'."}
        for (mode, field), (delta, span) in sorted(
            grouped.items(),
            key=lambda kv: (WHATIF_MODES.index(kv[0][0]), WHATIF_FIELDS.index(kv[0][1])),
        )
        if delta != 0
    ]
    if assumptions:
        joined = "; ".join(
            _format_whatif_delta(a["mode"], a["field"], a["delta"]) for a in assumptions
        )
        explanation = (
            f"Assumed: {joined}. "
            "The deterministic engine recomputes scores and ranking from these."
        )
    elif found_amount:
        explanation = (
            "Found an amount but could not identify which mode "
            "(sea, air, road, rail) it applies to; ranking unchanged."
        )
    else:
        explanation = (
            "No quantifiable change found in the question; ranking unchanged. "
            "Mention a mode and an amount, e.g. 'sea +6 hours' or 'rail saves $700'."
        )
    return {"assumptions": assumptions, "explanation": explanation}


def generate_whatif(
    question: str, ranked_options: list[dict], findings: list[dict]
) -> dict:
    """Return what-if assumptions, preferring Muse Wonder with fallback."""
    prompt = build_whatif_prompt(question, ranked_options, findings)
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        return {"source": "deterministic", **deterministic_whatif(question)}
    try:
        text = fetch_wonder_text(prompt, api_key)
        parsed = parse_whatif_response(text)
    except Exception:
        return {"source": "deterministic", **deterministic_whatif(question)}
    return {"source": "muse-wonder", **parsed}
