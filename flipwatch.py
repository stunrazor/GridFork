"""Flip-point analysis and flip watches: what the pick is betting on.

Same inputs, same ranking is reproducibility, not correctness. When the top
pick wins on an estimate while the runner-up has live data behind it, the
ranking must say so out loud — and name the exact boundary where the pick
changes. This module computes that boundary (item 3), states the pick's
provenance bet (items 1-2), and keeps watching live inputs for crossings
(item 4).

Everything here is pure and deterministic except the in-memory watch
registry, which is explicit demo-grade state: watches do not survive a
restart, and the API says so on every read.
"""

import orchestrator

# Scoring inputs a probe may move, in fixed probe order.
SCORING_FIELDS = (
    "delay_hours",
    "cost_usd",
    "on_time_probability",
    "confidence",
)

# Provenance strength: what the pick's edge rests on. Unknown labels fail
# closed into "weak" — unrecognized provenance is not trust.
STRONG_PROVENANCE = {"measured"}
MEDIUM_PROVENANCE = {"estimated-from-conditions"}
WEAK_PROVENANCE = {
    "estimated",
    "estimated-default",
    "estimated-fallback",
    "scenario",
}

# Only delay_hours moves under live feeds (marine, wind, air, road, rail
# layers all write delays); costs and probabilities are static estimates,
# so their flip points are reported but never live-watched.
LIVE_WATCHABLE_FIELDS = {"delay_hours"}

# A threshold reads "near" once the remaining distance to the flip value
# closes to this fraction of the full start-to-flip distance.
NEAR_FRACTION = 0.25

# Delay probes walk 1h steps out to +72h (worsen) or down to the 0h floor
# (improve); cost probes move in 5% steps out to a doubling/halving;
# probability probes move in 0.05 steps across half the 0..1 range.
MAX_DELAY_STEPS = 72
MAX_COST_STEPS = 20
MAX_PROB_STEPS = 10
PROB_STEP = 0.05


def _clamp_like_engine(field: str, value: float):
    """Mirror apply_whatif_assumptions clamping for one field value."""
    if field in ("delay_hours", "cost_usd"):
        return max(0, int(round(value)))
    return round(min(1.0, max(0.0, float(value))), 4)


def _cost_step(cost_usd: float) -> int:
    """One 5% cost probe step, at least 1 unit so small costs still move."""
    return max(1, int(round(cost_usd * 0.05)))


def scan_flip(
    rerank,
    base_top_id: str,
    mode: str,
    field: str,
    start_value: float,
    direction: int,
    step: float,
    max_steps: int,
) -> dict | None:
    """Walk one input until the rank-1 pick changes, or return None.

    ``rerank`` takes an assumptions list and returns ranked options.
    ``direction`` is +1 (worsen the top pick's input) or -1 (improve the
    runner-up's). Steps accumulate from ``start_value`` with engine
    clamping; the scan stops early at a clamp floor/ceiling. The first
    delta that changes rank-1 wins — correct because worsening the top
    pick's own input (or improving the runner-up's) only ever closes the
    score gap under the fixed-weight scorer.
    """
    deltas: list[dict] = []
    previous = _clamp_like_engine(field, start_value)
    for _ in range(max_steps):
        raw = start_value + direction * step * (len(deltas) + 1)
        applied = _clamp_like_engine(field, raw)
        if applied == previous:
            break
        previous = applied
        deltas.append({"mode": mode, "field": field, "delta": applied - start_value})
        ranked = rerank(deltas)
        if ranked[0]["option_id"] != base_top_id:
            return {
                "mode": mode,
                "field": field,
                "direction": direction,
                "start_value": start_value,
                "flip_value": applied,
                "flip_delta": round(applied - start_value, 4),
                "new_top_id": ranked[0]["option_id"],
            }
    return None


def _incident_rerank(scenario: dict):
    """Return a rerank closure over a fresh copy of an incident scenario."""
    baseline = scenario["baseline"]["storm_delay_hours_if_waiting"]

    def rerank(assumptions: list[dict]) -> list[dict]:
        updated = orchestrator.apply_whatif_assumptions(scenario, assumptions)
        findings = orchestrator.collect_findings(updated)
        options = orchestrator.build_options(findings, baseline)
        return orchestrator.score_options(options)

    return rerank


def _probe_specs(ranked: list[dict]) -> list[tuple]:
    """Probe specs for the top pick (worsen) and runner-up (improve)."""
    top, runner = ranked[0], ranked[1]
    specs = []
    for option, direction in ((top, 1), (runner, -1)):
        mode = option["mode"]
        # Delay starts come from the findings (ranked options carry time
        # saved, not delay), so flip_analysis fills them in; None here.
        specs.append((mode, "delay_hours", None, direction, 1, MAX_DELAY_STEPS))
        specs.append(
            (mode, "cost_usd", option["cost_usd"], direction,
             _cost_step(option["cost_usd"]), MAX_COST_STEPS)
        )
        specs.append(
            (mode, "on_time_probability", option["on_time_probability"],
             direction, PROB_STEP, MAX_PROB_STEPS)
        )
        specs.append(
            (mode, "confidence", option["confidence"], direction,
             PROB_STEP, MAX_PROB_STEPS)
        )
    return specs


def flip_analysis(
    ranked: list[dict],
    rerank,
    provenance: dict,
    finding_delay_by_mode: dict,
) -> dict:
    """Compute the decision boundary beside the rank-1 pick.

    ``finding_delay_by_mode`` maps each mode to its finding's delay_hours
    (ranked options carry time saved, not delay, so the scan start comes
    from the findings). Returns the margin, the provenance bet, the
    verdict sentence, every flip point found, and every probe range that
    held with no flip — holding is reported, never hidden.
    """
    top, runner = ranked[0], ranked[1]
    margin = round(top["score"] - runner["score"], 4)
    bet = {
        "top_option_id": top["option_id"],
        "runner_up_option_id": runner["option_id"],
        "top_backing": _backing(provenance, top["mode"]),
        "runner_up_backing": _backing(provenance, runner["mode"]),
    }
    flip_points: list[dict] = []
    held: list[dict] = []
    for mode, field, start, direction, step, max_steps in _probe_specs(ranked):
        if field == "delay_hours":
            start = finding_delay_by_mode[mode]
        else:
            option = top if mode == top["mode"] else runner
            start = option[field]
        found = scan_flip(
            rerank, top["option_id"], mode, field, start,
            direction, step, max_steps,
        )
        if found is None:
            held.append(
                {
                    "mode": mode,
                    "field": field,
                    "direction": direction,
                    "start_value": start,
                    "probed_steps": max_steps,
                    "result": "no flip in range",
                }
            )
        else:
            flip_points.append(found)
    flip_points.sort(
        key=lambda f: (f["mode"] != top["mode"], f["field"], abs(f["flip_delta"]))
    )
    verdict = _verdict(top, runner, margin, bet, flip_points)
    return {
        "top_option_id": top["option_id"],
        "runner_up_option_id": runner["option_id"],
        "margin": margin,
        "estimate_bet": bet,
        "verdict": verdict,
        "flip_points": flip_points,
        "held_without_flip": held,
    }


def _backing(provenance: dict, mode: str) -> dict:
    """Classify a mode's scoring inputs by provenance strength."""
    mode_prov = provenance.get(mode, {})
    backing = {"strong": [], "medium": [], "weak": []}
    for field in SCORING_FIELDS:
        label = mode_prov.get(field, "unknown")
        if label in STRONG_PROVENANCE:
            backing["strong"].append(field)
        elif label in MEDIUM_PROVENANCE:
            backing["medium"].append(field)
        else:
            backing["weak"].append(field)
    return backing


def _fields_phrase(fields: list[str]) -> str:
    """Join field names for the verdict sentence."""
    names = [("cost" if f == "cost_usd" else f.replace("_", " ")) for f in fields]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _verdict(
    top: dict,
    runner: dict,
    margin: float,
    bet: dict,
    flip_points: list[dict],
) -> str:
    """One deterministic paragraph: the pick, its bet, and what flips it."""
    top_backing = bet["top_backing"]
    runner_backing = bet["runner_up_backing"]
    sentence = f"{top['option_id']} wins by {margin} on score"
    top_weak = top_backing["weak"]
    runner_live = runner_backing["strong"] + runner_backing["medium"]
    if not top_weak:
        sentence += ", and its edge rests on measured inputs"
    elif runner_live:
        sentence += (
            f", but its edge rests on estimates "
            f"({top['mode']} {_fields_phrase(top_weak)}) while "
            f"{runner['option_id']}'s {_fields_phrase(runner_live)} "
            f"{'is' if len(runner_live) == 1 else 'are'} "
            f"grounded in live data"
        )
    else:
        sentence += (
            f", but its edge rests on estimates "
            f"({top['mode']} {_fields_phrase(top_weak)})"
        )
    sentence += "."
    if flip_points:
        first = flip_points[0]
        sentence += f" What would change it: {format_flip(first)}."
    else:
        sentence += " No single input moves the pick within probe range."
    return sentence


def format_flip(flip: dict) -> str:
    """One-line reading of a flip point."""
    field = flip["field"].replace("_", " ")
    delta = flip["flip_delta"]
    if flip["field"] == "delay_hours":
        return (
            f"{flip['mode']} delay {delta:+g}h "
            f"({flip['start_value']}h to {flip['flip_value']}h) flips the "
            f"pick to {flip['new_top_id']}"
        )
    if flip["field"] == "cost_usd":
        return (
            f"{flip['mode']} cost {delta:+,.0f} "
            f"(${flip['start_value']:,} to ${flip['flip_value']:,}) flips "
            f"the pick to {flip['new_top_id']}"
        )
    return (
        f"{flip['mode']} {field} {delta:+g} "
        f"({flip['start_value']} to {flip['flip_value']}) flips the pick "
        f"to {flip['new_top_id']}"
    )


def incident_flip(live: bool = False) -> dict:
    """Flip analysis for the North Sea incident, baseline or live.

    Baseline is pure (synthetic scenario, scenario provenance). Live runs
    the same computation over the current live snapshot's scenario and
    provenance, so the verdict reflects what the feeds actually say.
    """
    if live:
        parts = orchestrator._snapshot_parts()
        scenario, provenance = parts[0], parts[1]
        findings = orchestrator.collect_findings(scenario)
        options = orchestrator.build_options(
            findings, scenario["baseline"]["storm_delay_hours_if_waiting"]
        )
        ranked = orchestrator.score_options(options)
        data_mode = "live-snapshot"
        label = "Rotterdam → Oslo — live"
    else:
        scenario = orchestrator.load_scenario()
        findings = orchestrator.collect_findings(scenario)
        options = orchestrator.build_options(
            findings, scenario["baseline"]["storm_delay_hours_if_waiting"]
        )
        ranked = orchestrator.score_options(options)
        provenance = {
            mode: {field: "scenario" for field in SCORING_FIELDS}
            for mode in ("sea", "air", "road", "rail")
        }
        data_mode = "baseline"
        label = scenario["label"]
    delay_by_mode = {f["mode"]: f["delay_hours"] for f in findings}
    return {
        "label": label,
        "data_mode": data_mode,
        "ranked_options": ranked,
        "provenance": provenance,
        "flip": flip_analysis(
            ranked, _incident_rerank(scenario), provenance, delay_by_mode
        ),
    }


def live_delay_observed(scenario: dict) -> dict:
    """Current delay_hours per mode from a live snapshot's scenario."""
    return {
        mode: scenario["modes"][mode]["delay_hours"]
        for mode in ("sea", "air", "road", "rail")
    }


# In-memory watch registry. Demo-grade by design: creating a watch pins
# the current flip thresholds; re-checking compares fresh live delays
# against them. Nothing persists across restarts.
_WATCHES: dict = {}
_NEXT_WATCH_ID = 1


def reset_watches() -> None:
    """Clear the registry and restart ids (tests only)."""
    global _NEXT_WATCH_ID
    _WATCHES.clear()
    _NEXT_WATCH_ID = 1


def create_watch(label: str, analysis: dict, observed: dict) -> dict:
    """Pin one watch on a flip analysis plus current observed delays.

    Only delay_hours flip points become live thresholds — costs and
    probabilities have no live feed, so their flip points are recorded
    as static context the watch cannot move. ``observed`` maps mode to
    the current delay_hours for that mode.
    """
    global _NEXT_WATCH_ID
    watch_id = f"watch-{_NEXT_WATCH_ID}"
    _NEXT_WATCH_ID += 1
    thresholds = []
    for flip in analysis["flip_points"]:
        live = flip["field"] in LIVE_WATCHABLE_FIELDS
        thresholds.append(
            {
                "mode": flip["mode"],
                "field": flip["field"],
                "live": live,
                "direction": flip["direction"],
                "start_value": flip["start_value"],
                "flip_value": flip["flip_value"],
                "new_top_id": flip["new_top_id"],
                "status": "unknown",
                "observed": observed.get(flip["mode"]) if live else None,
            }
        )
    watch = {
        "watch_id": watch_id,
        "label": label,
        "top_option_id": analysis["top_option_id"],
        "runner_up_option_id": analysis["runner_up_option_id"],
        "verdict": analysis["verdict"],
        "checks": 0,
        "last_status": "unknown",
        "persistent": False,
        "thresholds": thresholds,
    }
    _WATCHES[watch_id] = watch
    return watch


def list_watches() -> list[dict]:
    """Return all watches in creation order."""
    return [_WATCHES[key] for key in sorted(_WATCHES)]


def get_watch(watch_id: str) -> dict | None:
    """Return one watch, or None when the id is unknown."""
    return _WATCHES.get(watch_id)


def _threshold_status(threshold: dict, observed: dict) -> tuple[str, object]:
    """Evaluate one threshold against observed delays.

    Live thresholds compare the observed delay to the flip value in the
    flip direction: crossed at or past it, near inside the final quarter
    of the start-to-flip distance, holding otherwise. Static thresholds
    have no feed, so they always report static-holding — the analysis
    stands until a human re-runs it.
    """
    if not threshold["live"]:
        return "static-holding", None
    value = observed.get(threshold["mode"])
    if value is None:
        return "unknown", None
    start, flip = threshold["start_value"], threshold["flip_value"]
    total = abs(flip - start)
    if threshold["direction"] >= 0:
        crossed = value >= flip
        remaining = flip - value
    else:
        crossed = value <= flip
        remaining = value - flip
    if crossed:
        return "crossed", value
    if total > 0 and remaining <= total * NEAR_FRACTION:
        return "near", value
    return "holding", value


def record_check(watch: dict, observed: dict) -> dict:
    """Re-check one watch against observed delays, storing the outcome."""
    statuses = []
    for threshold in watch["thresholds"]:
        status, value = _threshold_status(threshold, observed)
        threshold["status"] = status
        threshold["observed"] = value
        statuses.append(status)
    if "crossed" in statuses:
        overall = "flipped"
    elif "near" in statuses:
        overall = "near"
    elif statuses and all(s in ("holding", "static-holding") for s in statuses):
        overall = "holding"
    else:
        overall = "unknown"
    watch["checks"] += 1
    watch["last_status"] = overall
    return watch


def check_watch_live(watch_id: str) -> dict | None:
    """Re-fetch live delays and re-check one watch; None when unknown."""
    watch = get_watch(watch_id)
    if watch is None:
        return None
    scenario = orchestrator._snapshot_parts()[0]
    return record_check(watch, live_delay_observed(scenario))


def create_watch_live(label: str) -> dict:
    """Create one watch pinned on the current live snapshot."""
    parts = orchestrator._snapshot_parts()
    scenario, provenance = parts[0], parts[1]
    findings = orchestrator.collect_findings(scenario)
    options = orchestrator.build_options(
        findings, scenario["baseline"]["storm_delay_hours_if_waiting"]
    )
    ranked = orchestrator.score_options(options)
    delay_by_mode = {f["mode"]: f["delay_hours"] for f in findings}
    analysis = flip_analysis(
        ranked, _incident_rerank(scenario), provenance, delay_by_mode
    )
    return create_watch(label, analysis, live_delay_observed(scenario))
