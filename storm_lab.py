"""Scenario lab: corridor picker beside the GridFork demo.

Fully client-driven: pick a preset corridor or two custom places and run
its live snapshot; Ask grounds its answers in the corridor selected here.
Scenario tools (what-if, evidence, bench, illustration) live in the
route briefing.
"""

import ask_box
import geo


def _corridor_options() -> str:
    """Option tags for every preset, in geo single-source order."""
    return "".join(
        f'<option value="{cid}">{preset["label"]}</option>'
        for cid, preset in geo.CORRIDORS.items()
    )


_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GridFork scenario lab</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: -apple-system, "Segoe UI", Verdana, sans-serif;
         margin: 2rem auto; max-width: 72rem; padding: 0 1rem;
         color: #f4f7fb; background: #0b1526; line-height: 1.45; }
  a { color: #7dd3fc; }
  h1 { font-size: 1.4rem; margin-bottom: 0; }
  .sub { color: #c3cede; margin-top: 0.25rem; }
  h2 { font-size: 1.05rem; border-bottom: 1px solid #2a3a55;
       padding-bottom: 0.25rem; margin-top: 2rem; }
  table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
  th, td { border: 1px solid #2a3a55; padding: 0.35rem 0.5rem; text-align: left; }
  th { background: #1b2942; color: #c3cede; }
  button { font-size: 0.9rem; padding: 0.4rem 0.9rem; cursor: pointer;
           background: #1b2942; color: #f4f7fb; border: 1px solid #7dd3fc; }
  button:active { background: #274067; }
  input { font-size: 0.9rem; padding: 0.35rem 0.5rem; width: 60%;
          background: #0b1526; color: #f4f7fb; border: 1px solid #2a3a55; }
  select { font-size: 0.9rem; padding: 0.35rem 0.5rem;
           background: #0b1526; color: #f4f7fb; border: 1px solid #2a3a55; }
  .note { font-size: 0.85rem; color: #c3cede; }
  .ask-out { background: #131f33; border: 1px solid #2a3a55;
             padding: 0.6rem 0.8rem; margin-top: 0.5rem; min-height: 2.5rem;
             font-size: 0.9rem; }
  footer { margin-top: 2rem; font-size: 0.8rem; color: #c3cede;
           border-top: 1px solid #2a3a55; padding-top: 0.5rem; }
  code { background: #1b2942; padding: 0 0.25rem; }
  @media (max-width: 40rem) {
    body { font-size: 1.06rem; }
    .note, .sub, footer { font-size: 0.95rem; }
    button, input, select, table { font-size: 1rem; }
    th, td { padding: 0.45rem 0.6rem; }
    table { display: block; overflow-x: auto; }
  }
</style>
</head>
<body>
<h1>GridFork scenario lab</h1>
<p class="sub">Corridor picker with Ask grounded in your pick. Free-form
scenario questions live in the <a href="/demo/routes">route briefing</a>. <a href="/">Home</a> &middot;
<a href="/demo/grid">Back to the grid</a>.</p>

""" + ask_box.render_ask_box("lab", lead="Ask what-if questions against the selected corridor: change one disruption or assumption, then compare the before-and-after ranking.", example="What if the storm closes the port for 24 more hours?") + """<p id="lab-ask-context" class="note">Asking about: Rotterdam → Oslo (selected corridor).</p>
<h2>Worldwide snapshot</h2>
<p class="note">Live four-mode ranking for any corridor: pick a preset or
type two places. Runs the selected corridor on open and on click; Ask
above grounds its answers in the corridor selected here.</p>
<select id="lab-corridor">""" + _corridor_options() + """</select>
<input id="lab-from" placeholder="From (custom place)" style="width: 25%">
<input id="lab-to" placeholder="To (custom place)" style="width: 25%">
<button id="lab-snapshot-btn" type="button">Run live snapshot</button>
<div id="lab-snapshot-out" class="note">Loading default corridor…</div>

<h2>Change one assumption</h2>
<p class="note">Observed snapshot above; one hypothetical tweak below. The
engine rescores the selected corridor, so you compare observed reality
against exactly one change.</p>
<p><select id="lab-mode">
<option value="sea">Sea</option>
<option value="air">Air</option>
<option value="road">Road</option>
<option value="rail">Rail</option>
</select>
<select id="lab-field">
<option value="delay_hours">added delay (hours)</option>
<option value="cost_usd">added cost (USD)</option>
</select>
<input id="lab-delta" type="number" value="6" min="-48" max="100000" step="1">
<button id="lab-whatif-btn" type="button">Compare before/after</button></p>
<div id="lab-whatif-out" class="note">No hypothetical yet.</div>

<footer>
<p>Sources: deterministic scoring (always) &middot; live corridor legs
(measured when available, labeled estimates otherwise, provenance per
field) &middot; Ask GridFork (Spark/Wonder routing, paid, click only).
Scenario tools (what-if, evidence, bench, illustration) live in the
route briefing.</p>
</footer>

<script>
async function getJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(path + " -> " + r.status);
  return r.json();
}
function labCustomPair() {
  const f = document.getElementById("lab-from").value.trim();
  const t = document.getElementById("lab-to").value.trim();
  return (f && t) ? [f, t] : null;
}
function labAskContext() {
  const pair = labCustomPair();
  if (pair) return "&from=" + encodeURIComponent(pair[0]) + "&to=" + encodeURIComponent(pair[1]);
  return "&corridor=" + document.getElementById("lab-corridor").value;
}
function labSnapshotURL() {
  const pair = labCustomPair();
  if (pair) return "/snapshot?from=" + encodeURIComponent(pair[0]) + "&to=" + encodeURIComponent(pair[1]);
  return "/snapshot?corridor=" + document.getElementById("lab-corridor").value;
}
function labAskContextLabel() {
  const pair = labCustomPair();
  if (pair) return pair[0] + " → " + pair[1] + " (custom places)";
  const sel = document.getElementById("lab-corridor");
  return sel.options[sel.selectedIndex].text + " (selected corridor)";
}
function labRefreshAskContext(label) {
  document.getElementById("lab-ask-context").textContent =
    "Asking about: " + (label || labAskContextLabel()) + ".";
}
function labLegDetail(leg) {
  if (!leg.applicable) return leg.reason;
  if (leg.mode === "sea") return leg.wave_height_m + "m waves, " + leg.wind_kph + "kph wind [" + leg.marine_source + "/" + leg.wind_source + "]";
  if (leg.mode === "air") return (leg.airborne_origin + leg.airborne_dest) + " airborne near endpoints [" + leg.source + "]";
  if (leg.mode === "road") {
    const inc = leg.incidents ? ", " + leg.incidents.count + " incidents" : "";
    return "flow ratio " + leg.worst_ratio + inc + " [" + leg.source + "]";
  }
  return (leg.detail || "") + " [" + (leg.live ? "entur" : "estimated") + "]";
}
async function labRunSnapshot() {
  const el = document.getElementById("lab-snapshot-out");
  el.textContent = "Fetching live snapshot…";
  try {
    labAskSnapshot(await getJSON(labSnapshotURL()));
  } catch (e) { el.textContent = String(e); }
}
function labAskSnapshot(snap) {
  const el = document.getElementById("lab-snapshot-out");
  el.textContent = "";
    const head = document.createElement("p");
    head.textContent = snap.label + " (" + snap.distance_km + "km). Fastest alternate: " +
      snap.fastest_alternative.option_id + " (" + snap.fastest_alternative.total_hours + "h total).";
    el.appendChild(head);
    labRefreshAskContext(snap.label + " (" + snap.distance_km + "km, live)");
    const legs = document.createElement("table");
    const legHead = document.createElement("tr");
    ["Mode", "Status", "Live", "Delay", "Transit", "Detail"].forEach(t => {
      const th = document.createElement("th");
      th.textContent = t;
      legHead.appendChild(th);
    });
    legs.appendChild(legHead);
    ["sea", "air", "road", "rail"].forEach(mode => {
      const leg = snap.legs[mode];
      const tr = document.createElement("tr");
      [mode, leg.applicable ? leg.status : "n/a", leg.live ? "yes" : "no",
       leg.delay_hours === null ? "n/a" : "+" + leg.delay_hours + "h",
       leg.transit_hours === null ? "n/a" : leg.transit_hours + "h",
       labLegDetail(leg)].forEach(v => {
        const td = document.createElement("td");
        td.textContent = v;
        tr.appendChild(td);
      });
      legs.appendChild(tr);
    });
    el.appendChild(legs);
    const ranked = document.createElement("table");
    const rankHead = document.createElement("tr");
    ["Rank", "Mode", "Score", "Cost", "Time saved", "On-time"].forEach(t => {
      const th = document.createElement("th");
      th.textContent = t;
      rankHead.appendChild(th);
    });
    ranked.appendChild(rankHead);
    snap.ranked_options.forEach(o => {
      const tr = document.createElement("tr");
      [o.rank, o.mode, o.score, "$" + o.cost_usd, "+" + o.time_saved_hours + "h",
       o.on_time_probability].forEach(v => {
        const td = document.createElement("td");
        td.textContent = v;
        tr.appendChild(td);
      });
      ranked.appendChild(tr);
    });
    el.appendChild(ranked);
}
document.getElementById("lab-snapshot-btn").addEventListener("click", labRunSnapshot);
document.getElementById("lab-corridor").addEventListener("change", () => labRefreshAskContext());
document.getElementById("lab-from").addEventListener("input", () => labRefreshAskContext());
document.getElementById("lab-to").addEventListener("input", () => labRefreshAskContext());
labRefreshAskContext();
labRunSnapshot();
function labWhatifQuestion() {
  const mode = document.getElementById("lab-mode").value;
  const field = document.getElementById("lab-field").value;
  const delta = parseInt(document.getElementById("lab-delta").value, 10) || 0;
  if (field === "cost_usd")
    return "What if " + mode + " costs $" + Math.abs(delta) + " more?";
  if (delta < 0)
    return "What if " + mode + " saves " + Math.abs(delta) + " hours?";
  return "What if " + mode + " has " + delta + " more hours of delay?";
}
function labWhatifContext() {
  const pair = labCustomPair();
  if (pair) return "&from=" + encodeURIComponent(pair[0]) + "&to=" + encodeURIComponent(pair[1]);
  return "&corridor=" + document.getElementById("lab-corridor").value;
}
document.getElementById("lab-whatif-btn").addEventListener("click", async () => {
  const el = document.getElementById("lab-whatif-out");
  el.textContent = "Rescoring with one hypothetical change…";
  try {
    const q = labWhatifQuestion();
    const body = await getJSON("/demo/north-sea-storm/whatif?q=" +
      encodeURIComponent(q) + labWhatifContext());
    el.textContent = "";
    const hypo = document.createElement("p");
    hypo.textContent = "Hypothetical: " + body.whatif.explanation +
      " [" + body.whatif.source + "]";
    el.appendChild(hypo);
    const tops = document.createElement("p");
    const before = body.ranked_baseline[0];
    const after = body.ranked_options[0];
    tops.textContent = "Observed top: " + before.option_id + " (score " +
      before.score + ") → hypothetical top: " + after.option_id +
      " (score " + after.score + ").";
    el.appendChild(tops);
    const table = document.createElement("table");
    const head = document.createElement("tr");
    ["Option", "Observed rank/score", "Hypothetical rank/score"].forEach(t => {
      const th = document.createElement("th");
      th.textContent = t;
      head.appendChild(th);
    });
    table.appendChild(head);
    body.comparison.forEach(c => {
      const tr = document.createElement("tr");
      [c.option_id, c.rank_before + " / " + c.score_before,
       c.rank_after + " / " + c.score_after].forEach(v => {
        const td = document.createElement("td");
        td.textContent = v;
        tr.appendChild(td);
      });
      table.appendChild(tr);
    });
    el.appendChild(table);
  } catch (e) { el.textContent = String(e); }
});
</script>
""" + ask_box.render_ask_script("lab", extra=" + labAskContext()") + """</body>
</html>
"""


def render_storm_lab() -> str:
    """Return the scenario lab as a self-contained HTML document."""
    return _PAGE
