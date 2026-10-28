"""Orchestrator: deterministic scoring and ranking of reroute options.

Pure Python, no randomness, no clock, no network. Given the same findings,
the scores and ranking are always identical.
"""

import json
from pathlib import Path

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
