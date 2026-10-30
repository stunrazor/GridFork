"""Orchestrator: deterministic scoring and ranking of reroute options.

Pure Python, no randomness, no clock, no network. Given the same findings,
the scores and ranking are always identical.
"""

import json
from pathlib import Path

import sam_client
import spark_client
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
