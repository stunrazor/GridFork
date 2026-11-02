"""Orchestrator: deterministic scoring and ranking of reroute options.

Pure Python, no randomness, no clock, no network. Given the same findings,
the scores and ranking are always identical.
"""

import copy
import json
from pathlib import Path

import image_client
import live_air
import live_marine
import live_rail
import live_road
import live_weather
import openweights_client
import sam_client
import spark_client
import wonder_client
from agents import air, rail, road, sea

DATA_PATH = Path(__file__).resolve().parent / "data" / "synthetic_north_sea_storm.json"

# Fixed weights: cost, time saved, on-time probability, confidence.
WEIGHTS = {
    "cost": 0.30,
    "time_saved": 0.25,
    "on_time": 0.25,
    "confidence": 0.20,
}

OPTION_TITLES = {
    "sea-wait": "Wait out storm, then sail direct",
    "air-lift": "Air-lift urgent portion via AMS-OSL",
    "road-reroute": "Full-load truck reroute via Denmark",
    "rail-reroute": "Full-load intermodal rail via DE/DK/SE",
}


def load_scenario() -> dict:
    """Load the synthetic North Sea storm scenario."""
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def collect_findings(scenario: dict) -> list[dict]:
    """Run each mode agent over its synthetic slice, in fixed mode order."""
    modes = scenario["modes"]
    return [
        sea.analyze(modes["sea"]),
        air.analyze(modes["air"]),
        road.analyze(modes["road"]),
        rail.analyze(modes["rail"]),
    ]


def build_options(findings: list[dict], baseline_delay_hours: int) -> list[dict]:
    """Turn findings into reroute options with comparable numeric fields."""
    ids = {"sea": "sea-wait", "air": "air-lift", "road": "road-reroute", "rail": "rail-reroute"}
    options = []
    for finding in findings:
        option_id = ids[finding["mode"]]
        options.append(
            {
                "option_id": option_id,
                "title": OPTION_TITLES[option_id],
                "mode": finding["mode"],
                "synthetic": True,
                "cost_usd": finding["cost_usd"],
                "time_saved_hours": baseline_delay_hours - finding["delay_hours"],
                "on_time_probability": finding["on_time_probability"],
                "confidence": finding["confidence"],
            }
        )
    return options


def _normalize(values: list[float], higher_is_better: bool) -> list[float]:
    """Min-max normalize to 0..1; all-equal inputs all score 1.0."""
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0 for _ in values]
    if higher_is_better:
        return [(v - lo) / (hi - lo) for v in values]
    return [(hi - v) / (hi - lo) for v in values]


def score_options(options: list[dict]) -> list[dict]:
    """Attach deterministic weighted scores; ties break by option_id."""
    cost = _normalize([float(o["cost_usd"]) for o in options], higher_is_better=False)
    saved = _normalize([float(o["time_saved_hours"]) for o in options], higher_is_better=True)
    scored = []
    for option, cost_score, time_score in zip(options, cost, saved):
        score = (
            WEIGHTS["cost"] * cost_score
            + WEIGHTS["time_saved"] * time_score
            + WEIGHTS["on_time"] * option["on_time_probability"]
            + WEIGHTS["confidence"] * option["confidence"]
        )
        scored.append({**option, "score": round(score, 4)})
    scored.sort(key=lambda o: (-o["score"], o["option_id"]))
    for rank, option in enumerate(scored, start=1):
        option["rank"] = rank
    return scored


def run_demo() -> dict:
    """End-to-end demo: findings first, then ranked reroute options."""
    scenario = load_scenario()
    findings = collect_findings(scenario)
    options = build_options(findings, scenario["baseline"]["storm_delay_hours_if_waiting"])
    return {
        "scenario": scenario["scenario"],
        "synthetic": True,
        "label": scenario["label"],
        "findings": findings,
        "ranked_options": score_options(options),
    }


def run_demo_with_summary() -> dict:
    """Demo plus a narrative summary; falls back deterministically offline.

    The ranking itself is always the deterministic result. Only the attached
    ``summary`` dict may come from Muse Spark when ``META_MODEL_API_KEY`` is
    set and the API call succeeds.
    """
    demo = run_demo()
    demo["summary"] = spark_client.generate_summary(demo["ranked_options"])
    return demo


def run_demo_with_brief() -> dict:
    """Demo plus a structured cascade brief; falls back deterministically offline.

    The ranking itself is always the deterministic result. Only the attached
    ``brief`` dict may come from Muse Wonder when ``META_MODEL_API_KEY`` is
    set and the API call succeeds.
    """
    demo = run_demo()
    demo["brief"] = wonder_client.generate_brief(demo["ranked_options"], demo["findings"])
    return demo


# SAM visual ground truth for the sea leg. The default image is reference
# imagery (dense container stacks), not a live Rotterdam feed: the vision
# score corroborates port congestion for the demo narrative.
VISION_CONCEPT = "container"
VISION_DEFAULT_IMAGE_URL = (
    "https://unctad.org/sites/default/files/2023-03/"
    "20230322_NewsPic_PeruStory_shutterstock_2056090226_1200%20x%20675.jpg"
)
VISION_MAX_ADDED_DELAY_HOURS = 12


def run_demo_with_vision(image_url: str = VISION_DEFAULT_IMAGE_URL) -> dict:
    """Demo plus SAM visual ground truth blended into the sea leg.

    Blend rule: a live SAM result adds ``round(score * 12)`` delay hours to
    the sea finding before options are rebuilt and rescored, so the
    ``sea-wait`` numbers visibly move. Without a key, or when the API call
    fails, the ranking is identical to :func:`run_demo` and the ``vision``
    block reports ``source: "unavailable"``.
    """
    demo = run_demo()
    url = (image_url or "").strip() or VISION_DEFAULT_IMAGE_URL
    result = sam_client.segment_image(VISION_CONCEPT, url)
    detections = len(result["detections"])
    score = sam_client.congestion_score_from_counts({VISION_CONCEPT: detections})
    vision = {
        "source": result["source"],
        "concept": VISION_CONCEPT,
        "image_url": url,
        "reference_imagery": True,
        "detections": detections,
        "score": score,
        "sea_delay_added_hours": 0,
    }
    if result["source"] == "sam-3.1":
        added = round(score * VISION_MAX_ADDED_DELAY_HOURS)
        vision["sea_delay_added_hours"] = added
        scenario = load_scenario()
        findings = collect_findings(scenario)
        for finding in findings:
            if finding["mode"] == "sea":
                finding["delay_hours"] += added
                finding["vision_adjustment"] = (
                    f"+{added}h port congestion from SAM "
                    f"({detections} detections, score {score})"
                )
        options = build_options(findings, scenario["baseline"]["storm_delay_hours_if_waiting"])
        demo["findings"] = findings
        demo["ranked_options"] = score_options(options)
    demo["vision"] = vision
    return demo


def run_demo_with_image() -> dict:
    """Demo plus a Muse Image illustration; unavailable offline.

    The ranking itself is always the deterministic result. The attached
    ``image`` dict carries generated bytes only when ``META_MODEL_API_KEY``
    is set and the API call succeeds; otherwise it reports
    ``source: "unavailable"`` with no bytes.
    """
    demo = run_demo()
    scenario = load_scenario()
    sea = scenario["modes"]["sea"]
    demo["image"] = image_client.generate_scenario_image(
        scenario["label"], sea["wave_height_m"], sea["wind_kph"]
    )
    return demo


def run_demo_with_openweights(model_key: str = "spark-open") -> dict:
    """Demo plus an open-weight severity classification; setup-safe offline.

    The ranking itself is always the deterministic result. The attached
    ``openweights`` dict carries model text only when a runner is
    configured and answers; otherwise it reports ``setup-required`` or
    ``unreachable`` with no network call beyond the single attempt.
    """
    demo = run_demo()
    prompt = openweights_client.build_severity_prompt(demo["findings"])
    demo["openweights"] = openweights_client.generate_text(model_key, prompt)
    return demo


# Fields a what-if assumption may adjust, with their clamp rules applied in
# apply_whatif_assumptions: delays and costs floor at zero, probabilities
# stay in 0..1.
WHATIF_ADJUSTABLE_FIELDS = (
    "delay_hours",
    "cost_usd",
    "on_time_probability",
    "confidence",
)


def apply_whatif_assumptions(scenario: dict, assumptions: list[dict]) -> dict:
    """Return a copy of scenario with assumption deltas added in.

    Unknown modes, fields, or non-numeric deltas are skipped so one bad
    entry can never corrupt the recompute. The input scenario is untouched.
    """
    updated = copy.deepcopy(scenario)
    modes = updated.get("modes", {})
    for item in assumptions or []:
        if not isinstance(item, dict):
            continue
        mode, field, delta = item.get("mode"), item.get("field"), item.get("delta")
        if mode not in modes or not isinstance(modes[mode], dict):
            continue
        if field not in WHATIF_ADJUSTABLE_FIELDS:
            continue
        if isinstance(delta, bool) or not isinstance(delta, (int, float)):
            continue
        current = modes[mode].get(field)
        if isinstance(current, bool) or not isinstance(current, (int, float)):
            continue
        value = current + delta
        if field in ("delay_hours", "cost_usd"):
            modes[mode][field] = max(0, int(round(value)))
        else:
            modes[mode][field] = round(min(1.0, max(0.0, float(value))), 4)
    return updated


MAX_ASK_CHARS = 500

# Scenario/explanation questions go to Wonder; everything else (costs,
# delays, statuses, sources) goes to Spark. Matched on padded lowercase
# text so short triggers need word boundaries ("why", not "anyway").
WONDER_TRIGGERS = (
    "what if",
    "whatif",
    "suppose",
    "scenario",
    "explain",
    "why",
    "reason",
    "cascade",
    "predict",
    "forecast",
    "would happen",
    "impact of",
)

# Representative ranked option per mode for the fastest-alternate readout.
MODE_OPTION_IDS = {
    "sea": "sea-wait",
    "air": "air-lift",
    "road": "road-reroute",
    "rail": "rail-reroute",
}


def route_ask(question: str) -> tuple[str, str]:
    """Route a question to a model, returning (model, reason)."""
    padded = f" {(question or '').lower()} "
    for trigger in WONDER_TRIGGERS:
        if f" {trigger} " in padded or padded.strip().startswith(trigger + " "):
            return "wonder", f"matched '{trigger}'"
    return "spark", "default factual routing"


def fastest_alternative(scenario: dict) -> dict:
    """Fastest mode by total journey time (transit plus delay hours).

    Deterministic over the snapshot slices; ties resolve in
    sea/air/road/rail order. Sea transit comes from the baseline plan.
    """
    modes = scenario["modes"]
    totals = {}
    for mode in ("sea", "air", "road", "rail"):
        transit = (
            scenario["baseline"]["planned_sea_transit_hours"]
            if mode == "sea"
            else modes[mode]["transit_hours"]
        )
        totals[mode] = (transit, modes[mode]["delay_hours"])
    # min keeps the first minimal item: dict order is sea/air/road/rail.
    mode = min(totals, key=lambda m: totals[m][0] + totals[m][1])
    transit, delay = totals[mode]
    return {
        "mode": mode,
        "option_id": MODE_OPTION_IDS[mode],
        "total_hours": round(transit + delay, 1),
        "transit_hours": transit,
        "delay_hours": delay,
    }


def run_ask(question: str) -> dict:
    """Answer one question about the incident via Muse Spark.

    The model answers only from the live snapshot — ranking, findings,
    measured conditions, and provenance (see
    :func:`spark_client.build_ask_prompt`); without a key or on failure
    the answer reports ``setup-required`` / ``unavailable`` with no
    invented text. Raises ValueError on a blank or overlong question.
    """
    asked = (question or "").strip()
    if not asked:
        raise ValueError("Ask a question about this incident and ranking.")
    if len(asked) > MAX_ASK_CHARS:
        raise ValueError(f"Question exceeds the {MAX_ASK_CHARS}-character cap.")
    scenario, provenance, marine, wind, air, road, rail = _snapshot_parts()
    findings = collect_findings(scenario)
    options = build_options(
        findings, scenario["baseline"]["storm_delay_hours_if_waiting"]
    )
    ranked = score_options(options)
    live = {
        "provenance": provenance,
        "marine": marine,
        "wind": wind,
        "air": air,
        "road": road,
        "rail": rail,
    }
    routed_to, reason = route_ask(asked)
    if routed_to == "wonder":
        answer = wonder_client.answer_ask(
            asked, findings, ranked, live=live
        )
    else:
        answer = spark_client.answer_question(
            asked, findings, ranked, live=live
        )
    return {
        "question": asked,
        "routed_to": routed_to,
        "reason": reason,
        "answer": answer,
        "fastest_alternative": fastest_alternative(scenario),
    }


def run_whatif(question: str) -> dict:
    """Answer a what-if question with before/after deterministic rankings.

    Muse Wonder (or the deterministic parser offline) turns the question
    into explicit assumptions; the existing deterministic engine then
    recomputes findings, scores, and ranking from the adjusted scenario.
    The model never scores or ranks. Raises ValueError on a blank question.
    """
    asked = (question or "").strip()
    if not asked:
        raise ValueError(
            "Ask a what-if question, e.g. "
            "'What if Rotterdam closes for six more hours?'"
        )
    baseline = run_demo()
    whatif = wonder_client.generate_whatif(
        asked, baseline["ranked_options"], baseline["findings"]
    )
    scenario = apply_whatif_assumptions(load_scenario(), whatif["assumptions"])
    findings_after = collect_findings(scenario)
    options_after = build_options(
        findings_after, scenario["baseline"]["storm_delay_hours_if_waiting"]
    )
    ranked_after = score_options(options_after)
    before_by_id = {o["option_id"]: o for o in baseline["ranked_options"]}
    comparison = []
    for option in ranked_after:
        before = before_by_id[option["option_id"]]
        comparison.append(
            {
                "option_id": option["option_id"],
                "title": option["title"],
                "score_before": before["score"],
                "score_after": option["score"],
                "score_delta": round(option["score"] - before["score"], 4),
                "rank_before": before["rank"],
                "rank_after": option["rank"],
            }
        )
    return {
        "scenario": baseline["scenario"],
        "synthetic": True,
        "label": baseline["label"],
        "question": asked,
        "whatif": whatif,
        "ranked_baseline": baseline["ranked_options"],
        "findings_after": findings_after,
        "ranked_options": ranked_after,
        "comparison": comparison,
    }


# Fixed synthetic storm cases for the open-weight route challenge. Every
# model critiques the same cases; the last one flips the deterministic top
# pick from rail to road, so agreement is a real signal, not a given.
CHALLENGE_CASES = (
    {
        "case_id": "baseline",
        "label": "Baseline North Sea storm (synthetic)",
        "assumptions": [],
    },
    {
        "case_id": "rotterdam-plus-6h",
        "label": "Rotterdam closure extended six hours (synthetic)",
        "assumptions": [
            {
                "mode": "sea",
                "field": "delay_hours",
                "delta": 6,
                "reason": "Challenge case: port closure extended.",
            }
        ],
    },
    {
        "case_id": "rail-plus-30h",
        "label": "Rail corridor blocked thirty extra hours (synthetic)",
        "assumptions": [
            {
                "mode": "rail",
                "field": "delay_hours",
                "delta": 30,
                "reason": "Challenge case: rail corridor blocked.",
            }
        ],
    },
)

CHALLENGE_AUTHORITATIVE_NOTE = (
    "Deterministic ranking is authoritative; model critiques are advisory."
)


# Fixed canned critique for offline mock previews. It always prefers rail,
# so the mock agrees on the first two cases and misses the road flip on the
# third — exercising the real agreement computation without any network use.
MOCK_CRITIQUE_TEXT = (
    '{"agree_with_top_pick": true, '
    '"preferred_option_id": "rail-reroute", '
    '"concerns": ["Mock critique for offline preview"], "confidence": 0.7}'
)


def _mock_challenge_completion(model_key: str, prompt: str) -> dict:
    """Return a canned completion; never touches the network or runners."""
    _ = (model_key, prompt)
    return {
        "model": model_key,
        "source": "mock",
        "text": MOCK_CRITIQUE_TEXT,
        "latency_ms": None,
        "usage": None,
    }


def run_challenge(
    model_keys: tuple[str, ...] | list[str] = ("spark-open", "glimmer"),
    timeout: float = 300.0,
    mock: bool = False,
) -> dict:
    """Run the route challenge: each model critiques each fixed storm case.

    Agreement means the model's preferred option matches the deterministic
    rank-1 pick. A model failure (unconfigured runner, unreachable server,
    invalid JSON) marks that entry accordingly and never raises; only an
    unknown model key raises ValueError. With ``mock=True`` every entry
    uses fixed canned critiques labeled ``source: "mock"`` and no network
    call is attempted.
    """
    keys = list(model_keys)
    for key in keys:
        if key not in openweights_client.MODELS:
            raise ValueError(f"unknown open-weight model: {key!r}")
    base = run_demo()
    cases = []
    for spec in CHALLENGE_CASES:
        scenario = apply_whatif_assumptions(load_scenario(), spec["assumptions"])
        findings = collect_findings(scenario)
        ranked = score_options(
            build_options(
                findings, scenario["baseline"]["storm_delay_hours_if_waiting"]
            )
        )
        cases.append(
            {
                "case_id": spec["case_id"],
                "label": spec["label"],
                "assumptions": spec["assumptions"],
                "deterministic_top": ranked[0]["option_id"],
                "findings": findings,
                "ranked_options": ranked,
            }
        )
    results = []
    for key in keys:
        for case in cases:
            prompt = openweights_client.build_critique_prompt(
                case["label"], case["findings"], case["ranked_options"]
            )
            if mock:
                completion = _mock_challenge_completion(key, prompt)
            else:
                completion = openweights_client.complete_with_metrics(
                    key, prompt, timeout=timeout
                )
            entry = {
                "case_id": case["case_id"],
                "model": key,
                "source": completion["source"],
                "advisory": True,
                "schema_valid": False,
                "agrees_with_ranking": None,
                "deterministic_top": case["deterministic_top"],
                "preferred_option_id": None,
                "agree_flag": None,
                "confidence": None,
                "concerns": [],
                "latency_ms": completion["latency_ms"],
                "usage": completion["usage"],
                "error": None,
            }
            if completion["source"] in ("openweights-local", "mock"):
                try:
                    critique = openweights_client.parse_critique_response(
                        completion["text"],
                        [o["option_id"] for o in case["ranked_options"]],
                    )
                except ValueError as exc:
                    entry["error"] = f"invalid critique JSON: {exc}"
                else:
                    entry["schema_valid"] = True
                    entry["agrees_with_ranking"] = (
                        critique["preferred_option_id"] == case["deterministic_top"]
                    )
                    entry["preferred_option_id"] = critique["preferred_option_id"]
                    entry["agree_flag"] = critique["agree_with_top_pick"]
                    entry["confidence"] = critique["confidence"]
                    entry["concerns"] = critique["concerns"]
            else:
                entry["error"] = completion.get("detail")
            results.append(entry)
    summary = []
    for key in keys:
        model_results = [r for r in results if r["model"] == key]
        valid = [r for r in model_results if r["schema_valid"]]
        agreements = sum(1 for r in valid if r["agrees_with_ranking"])
        token_totals = [
            r["usage"]["total_tokens"]
            for r in model_results
            if r["usage"] and r["usage"].get("total_tokens") is not None
        ]
        latencies = [r["latency_ms"] for r in model_results if r["latency_ms"] is not None]
        summary.append(
            {
                "model": key,
                "label": openweights_client.MODELS[key]["label"],
                "cases": len(model_results),
                "schema_valid": len(valid),
                "schema_valid_rate": round(len(valid) / len(model_results), 4),
                "agreements": agreements,
                "agreement_rate": round(agreements / len(valid), 4) if valid else None,
                "total_tokens": sum(token_totals) if token_totals else None,
                "avg_latency_ms": (
                    round(sum(latencies) / len(latencies), 1) if latencies else None
                ),
            }
        )
    return {
        "scenario": base["scenario"],
        "synthetic": True,
        "label": base["label"],
        "authoritative": CHALLENGE_AUTHORITATIVE_NOTE,
        "cases": cases,
        "results": results,
        "summary": summary,
    }


# Phase 1 live data: measured sea conditions drive the sea slice through
# this explicit rule, aligned with the sea agent's own thresholds
# (disrupted at 8m/100kph, degraded from 12h delay). Costs, on-time
# probabilities, and confidences stay synthetic estimates — no free
# real-time source exists — and provenance says so per field.
def _sea_conditions_to_delay(
    wave_height_m: float, wind_kph: float
) -> tuple[int, str]:
    """Map measured conditions to (delay_hours, port_status)."""
    if wave_height_m >= 8 or wind_kph >= 100:
        return 48, "Rotterdam departures restricted"
    if wave_height_m >= 4 or wind_kph >= 60:
        return 12, "Rotterdam departures advisory"
    return 2, "Rotterdam departures normal"


def build_live_scenario() -> tuple[dict, dict, dict, dict]:
    """Build a scenario with live sea conditions, plus provenance and readouts.

    Wave height and wind come from Open-Meteo (or labeled fallbacks); the
    sea delay and port status are estimated from them by rule; everything
    else keeps its synthetic value. Provenance values: "measured",
    "estimated-from-conditions", "synthetic", "synthetic-fallback".
    Returns (scenario, provenance, marine_readout, wind_readout).
    """
    scenario = load_scenario()
    marine = live_marine.fetch_north_sea_waves()
    wind = live_weather.fetch_rotterdam_wind()
    wave_prov = "measured" if marine["live"] else "synthetic-fallback"
    wind_prov = "measured" if wind["live"] else "synthetic-fallback"
    if marine["live"] or wind["live"]:
        wave = marine["wave_height_m"]
        wind_kph = wind["wind_kph"]
        delay_hours, port_status = _sea_conditions_to_delay(wave, wind_kph)
        sea_slice = scenario["modes"]["sea"]
        sea_slice["wave_height_m"] = wave
        sea_slice["wind_kph"] = wind_kph
        sea_slice["delay_hours"] = delay_hours
        sea_slice["port_status"] = port_status
        delay_prov = "estimated-from-conditions"
    else:
        # Fully offline: leave the synthetic slice byte-identical so the
        # snapshot equals the baseline demo exactly.
        delay_prov = "synthetic-fallback"
    provenance = {
        "sea": {
            "wave_height_m": wave_prov,
            "wind_kph": wind_prov,
            "delay_hours": delay_prov,
            "port_status": delay_prov,
            "cost_usd": "synthetic-estimate",
            "on_time_probability": "synthetic-estimate",
            "confidence": "synthetic-estimate",
        },
    }
    for mode in ("air", "road", "rail"):
        provenance[mode] = {
            "delay_hours": "synthetic",
            "cost_usd": "synthetic",
            "on_time_probability": "synthetic",
            "confidence": "synthetic",
        }
    return scenario, provenance, marine, wind


def run_live_snapshot() -> dict:
    """Rank the live snapshot: measured conditions through the same engine.

    Identical scoring and ranking code as :func:`run_demo`; only the sea
    inputs (Phase 1) and the air/road/rail inputs (Phase 2) may be
    measured. Fully offline with no Phase 2 keys this equals the baseline
    demo exactly, with every sea field marked synthetic-fallback and each
    Phase 2 layer reporting setup-required.
    """
    scenario, provenance, marine, wind, air, road, rail = _snapshot_parts()
    findings = collect_findings(scenario)
    options = build_options(findings, scenario["baseline"]["storm_delay_hours_if_waiting"])
    return {
        "scenario": scenario["scenario"],
        "synthetic": False,
        "data_mode": "live-snapshot",
        "label": scenario["label"],
        "marine": marine,
        "wind": wind,
        "air": air,
        "road": road,
        "rail": rail,
        "provenance": provenance,
        "findings": findings,
        "ranked_options": score_options(options),
    }


def _snapshot_parts() -> tuple:
    """Fetch and apply all live layers; shared by snapshot and ask."""
    scenario, provenance, marine, wind = build_live_scenario()
    air, road, rail = fetch_phase2_layers()
    apply_phase2_layers(scenario, provenance, air, road, rail)
    return scenario, provenance, marine, wind, air, road, rail


# Phase 2 live data: measured air/road/rail conditions drive those slices
# through these explicit rules, aligned with each agent's own threshold
# (available below 12h delay, degraded at 12h+). Costs, on-time
# probabilities, and confidences stay synthetic estimates — no free
# real-time source exists — and provenance says so per field. Layers
# without a configured key leave their slices byte-identical, exactly
# like the offline Phase 1 path.
def _observed_traffic_to_air_delay(airborne_total: int) -> int | None:
    """Map observed AMS+OSL traffic to air delay hours.

    Returns None when nothing is airborne: zero traffic is ambiguous
    (night ops vs coverage gap), so the engine declines to estimate and
    the synthetic delay stands.
    """
    if airborne_total >= 10:
        return 4
    if airborne_total >= 1:
        return 8
    return None


def _congestion_to_road_delay(worst_ratio: float) -> int:
    """Map worst current/free-flow speed ratio to road delay hours."""
    if worst_ratio >= 0.75:
        return 6
    if worst_ratio >= 0.5:
        return 10
    return 14


def _incidents_to_road_floor(closures: int, majors: int) -> int:
    """Map incident counts to a delay floor; incidents never lower delay."""
    if closures >= 1:
        return 14
    if majors >= 1:
        return 12
    return 0


def _road_incident_floor(road: dict) -> int:
    """Incident delay floor, applied only when corroborated.

    Raw incident counts cover whole metro areas, so a closure floors the
    road leg only when congestion or routed delay shows its effect;
    otherwise the counts stay advisory context. Live-learned: free flow
    plus hundreds of metro closures must not degrade the corridor.
    """
    incidents = road.get("incidents")
    if not incidents:
        return 0
    route = road.get("route") or {}
    corroborated = (
        road["worst_ratio"] < 0.75 or route.get("traffic_delay_hours", 0) > 0
    )
    if not corroborated:
        return 0
    return _incidents_to_road_floor(incidents["closures"], incidents["majors"])


def _disruptions_to_rail_delay(active: int, severe: int) -> int:
    """Map unified rail disruption counts to rail delay hours.

    Severe means Rotterdam mentions for NS, cancellations for DB.
    """
    if severe >= 1:
        return 12
    if active >= 1:
        return 8
    return 4


def fetch_phase2_layers() -> tuple[dict, dict, dict]:
    """Fetch the Phase 2 live layers: (air, road, rail) readouts."""
    return (
        live_air.fetch_air_traffic(),
        live_road.fetch_corridor_congestion(),
        live_rail.fetch_rail_disruptions(),
    )


def apply_phase2_layers(
    scenario: dict, provenance: dict, air: dict, road: dict, rail: dict
) -> None:
    """Apply live Phase 2 readouts to a scenario in place.

    Only readouts with ``live: True`` touch their slice; setup-required
    and fallback layers leave values and provenance exactly as they were.
    """
    if air.get("live"):
        air_slice = scenario["modes"]["air"]
        air_slice["airborne_ams"] = air["airborne_ams"]
        air_slice["airborne_osl"] = air["airborne_osl"]
        provenance["air"]["airborne_ams"] = "measured"
        provenance["air"]["airborne_osl"] = "measured"
        delay = _observed_traffic_to_air_delay(
            air["airborne_ams"] + air["airborne_osl"]
        )
        if delay is not None:
            air_slice["delay_hours"] = delay
            provenance["air"]["delay_hours"] = "estimated-from-conditions"
    if road.get("live"):
        road_slice = scenario["modes"]["road"]
        road_slice["worst_congestion_ratio"] = road["worst_ratio"]
        delay = _congestion_to_road_delay(road["worst_ratio"])
        if road.get("incidents"):
            incidents = road["incidents"]
            road_slice["incident_count"] = incidents["count"]
            road_slice["closure_count"] = incidents["closures"]
            delay = max(delay, _road_incident_floor(road))
            provenance["road"]["incident_count"] = "measured"
            provenance["road"]["closure_count"] = "measured"
        if road.get("route"):
            route = road["route"]
            road_slice["distance_km"] = route["distance_km"]
            road_slice["transit_hours"] = route["transit_hours"]
            road_slice["traffic_delay_hours"] = route["traffic_delay_hours"]
            delay = max(delay, round(route["traffic_delay_hours"]))
            provenance["road"]["distance_km"] = "measured"
            provenance["road"]["transit_hours"] = "measured"
            provenance["road"]["traffic_delay_hours"] = "measured"
        road_slice["delay_hours"] = delay
        provenance["road"]["worst_congestion_ratio"] = "measured"
        provenance["road"]["delay_hours"] = "estimated-from-conditions"
    if rail.get("live"):
        rail_slice = scenario["modes"]["rail"]
        rail_slice["active_disruptions"] = rail["active_count"]
        rail_slice["severe_disruptions"] = rail["severe_count"]
        rail_slice["delay_hours"] = _disruptions_to_rail_delay(
            rail["active_count"], rail["severe_count"]
        )
        provenance["rail"]["active_disruptions"] = "measured"
        provenance["rail"]["severe_disruptions"] = "measured"
        provenance["rail"]["delay_hours"] = "estimated-from-conditions"
