"""Minimal observable grid: one page showing the demo the agents produce.

Plain server-rendered shell plus small fetches to the JSON endpoints. Works
offline (every endpoint falls back deterministically); the Meta Models
section runs on demand so a page load never triggers a live Wonder or
runner call. Scenario tools (what-if, evidence, bench, illustration)
live in the route briefing.
"""

import ask_box


def render_grid_page() -> str:
    """Return the full grid page as a self-contained HTML document."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GridFork live grid</title>
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
  .modes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem; }
  .mode { background: #131f33; border: 1px solid #2a3a55; padding: 0.6rem 0.75rem; }
  .mode h3 { margin: 0 0 0.3rem; font-size: 0.95rem; }
  .pill { display: inline-block; font-size: 0.75rem; font-weight: bold;
          padding: 0.1rem 0.5rem; border: 1px solid #666; }
  .disrupted { background: #b3261e; color: #fff; border-color: #b3261e; }
  .degraded { background: #8a5a00; color: #fff; border-color: #8a5a00; }
  .available { background: #1e7e34; color: #fff; border-color: #1e7e34; }
  table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
  th, td { border: 1px solid #2a3a55; padding: 0.35rem 0.5rem; text-align: left; }
  th { background: #1b2942; color: #c3cede; }
  tr.top td { font-weight: bold; color: #7dd3fc; }
  button { font-size: 0.9rem; padding: 0.4rem 0.9rem; cursor: pointer;
           background: #1b2942; color: #f4f7fb; border: 1px solid #7dd3fc; }
  button:active { background: #274067; }
  input { font-size: 0.9rem; padding: 0.35rem 0.5rem; width: 65%;
          background: #0b1526; color: #f4f7fb; border: 1px solid #2a3a55; }
  h3 { font-size: 0.95rem; margin: 1.25rem 0 0.25rem; }
  .note { font-size: 0.85rem; color: #c3cede; }
  .ask-out { background: #131f33; border: 1px solid #2a3a55;
             padding: 0.6rem 0.8rem; margin-top: 0.5rem; min-height: 2.5rem;
             font-size: 0.9rem; }
  .src { font-size: 0.8rem; color: #c3cede; }
  .mode-card { background: #131f33; border: 1px solid #2a3a55;
              padding: 0.7rem 0.85rem; }
  .mode-card h3 { margin: 0 0 0.3rem; font-size: 1rem; text-transform: capitalize; }
  .mode-card .big { font-size: 1.1rem; font-weight: bold; margin: 0.25rem 0; }
  .mode-card .meta { font-size: 0.82rem; color: #c3cede; }
  .opt-cards { display: grid; gap: 0.6rem; }
  .opt-card { background: #131f33; border: 1px solid #2a3a55;
             padding: 0.6rem 0.8rem; }
  .opt-card.top { border-color: #7dd3fc; border-width: 2px; }
  .opt-card .nums { color: #7dd3fc; }
  .lbl { display: inline-block; font-size: 0.72rem; font-weight: bold;
         padding: 0.1rem 0.45rem; border: 1px solid #666; margin-left: 0.3rem; }
  .lbl-live { border-color: #4ade80; color: #4ade80; }
  .lbl-est { border-color: #f5b942; color: #f5b942; }
  .lbl-una { border-color: #666; color: #c3cede; }
  details.evidence { margin-top: 2rem; border: 1px solid #2a3a55;
                    background: #131f33; padding: 0.6rem 0.9rem; }
  details.evidence summary { cursor: pointer; font-size: 1rem; font-weight: bold; }
  footer { margin-top: 2rem; font-size: 0.8rem; color: #c3cede;
           border-top: 1px solid #2a3a55; padding-top: 0.5rem; }
  code { background: #1b2942; padding: 0 0.25rem; }
  @media (max-width: 60rem) { .modes { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 40rem) {
    body { font-size: 1.06rem; }
    .modes { grid-template-columns: 1fr; }
    .note, .sub, footer, .mode-card .meta { font-size: 0.95rem; }
    button, input { font-size: 1rem; }
  }
</style>
</head>
<body>
<h1>GridFork live grid</h1>
<p class="sub">Multi-agent reroute engine: live traffic, weather &amp; disruption data across sea, air, road and rail. Legs measured live; costs stay estimates.
Open the <a href="/demo/north-sea-storm/brief-card">shareable incident brief</a>,
the <a href="/demo/storm-lab">scenario lab</a>, the
<a href="/demo/routes">route briefing</a>, or <a href="/">home</a>.</p>

""" + ask_box.render_ask_box("grid", lead="Ask what's happening now across sea, air, road, and rail: live conditions and disruptions on this grid, for any corridor worldwide.", example="Which mode is disrupted right now, and why?") + """<p id="grid-ask-context" class="note">Asking about: North Sea incident &mdash; or name any two places to ask worldwide.</p>
<h2>Specialist findings</h2>
<div class="modes" id="modes"><p class="note">Loading&hellip;</p></div>

<h2>Ranked reroutes</h2>
<div class="opt-cards" id="ranking"><p class="note">Loading&hellip;</p></div>
<p class="note">Scenario tools &mdash; what-if, evidence, bench, illustration
&mdash; live in the <a href="/demo/routes">route briefing</a>.</p>

<h2>Narrative summary</h2>
<p id="summary" class="note">Loading&hellip;</p>

<h2>Live snapshot</h2>
<p class="note">Phase 1 real data: measured North Sea waves and Rotterdam wind
drive the sea leg through the same engine. Phase 2 air, road, and rail layers
(OpenSky/adsb.lol traffic, TomTom congestion plus incidents and routed
transit, rail disruptions via NS, DB, or keyless Entur) join the snapshot;
keyed layers without keys stay estimated and report setup-required.
Costs and probabilities stay estimates; provenance is shown per
field. Loads live on open; the button flips back to the baseline.</p>
<button id="live-btn" type="button">Switch live/baseline view</button>
<p id="live" class="note">Loading live values…</p>

<details class="evidence">
<summary>AI analysis and evidence (optional)</summary>
<p class="note">On-demand extras. Nothing here runs on page load. The Wonder
explanation is a paid Meta API call; open weights need a local runner.</p>
<h3>Muse Wonder &mdash; decision explanation</h3>
<p class="note">Grounded in the current findings and ranking.</p>
<button id="brief-btn" type="button">Explain this scenario</button>
<p id="brief" class="note">Not run yet.</p>
<h3>Open weights &mdash; runner setup</h3>
<p class="note">Muse Spark Open and Muse Glimmer run on your own hardware.
These buttons only check runner setup; they start nothing.</p>
<button id="ow-spark-btn" type="button">Check Spark Open runner</button>
<button id="ow-glimmer-btn" type="button">Check Glimmer runner</button>
<p id="ow-spark" class="note">Not checked yet.</p>
<p id="ow-glimmer" class="note">Not checked yet.</p>
<button id="ow-ask-spark-btn" type="button">Classify with Spark Open</button>
<button id="ow-ask-glimmer-btn" type="button">Classify with Glimmer</button>
<p id="ow-ask-spark" class="note">Not run yet.</p>
<p id="ow-ask-glimmer" class="note">Not run yet.</p>
</details>
<footer>
<p>Sources: deterministic scoring (always) &middot; Muse Spark summary
(<code>source: muse-spark</code> live, <code>deterministic</code> offline) &middot;
Open-Meteo wind (<code>live: true</code>) or a labeled fallback &middot; Muse Wonder
brief (<code>muse-wonder</code> live, <code>deterministic</code> offline)
&middot; open weights
(<code>setup-required</code> until a runner is configured) &middot; Phase 2
air/road/rail (<code>setup-required</code> until free keys are set).
Scenario tools (what-if, evidence, bench, illustration) live in the
route briefing.</p>
</footer>

<script>
async function getJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(path + " -> " + r.status);
  return r.json();
}
function pill(status) {
  return '<span class="pill ' + status + '">' + status + '</span>';
}
function layerInfo(demo, mode) {
  const byMode = {sea: [demo.marine, demo.wind], air: [demo.air],
    road: [demo.road], rail: [demo.rail]};
  const present = (byMode[mode] || []).filter(Boolean);
  if (!present.length)
    return {sources: "reference incident", updated: "n/a",
      label: "Estimated", cls: "lbl-est"};
  const sources = present.map(l => l.source).join(" / ");
  const stamps = present.map(l => l.observed_at).filter(Boolean).sort();
  const live = present.some(l => l.live);
  const na = present.every(l => l.source === "not-applicable");
  return {
    sources: sources,
    updated: stamps.length ? stamps[stamps.length - 1] : "unknown",
    label: live ? "Live" : (na ? "Unavailable" : "Estimated"),
    cls: live ? "lbl-live" : (na ? "lbl-una" : "lbl-est")
  };
}
function renderDemo(demo) {
  document.getElementById("modes").innerHTML = demo.findings.map(f => {
    const info = layerInfo(demo, f.mode);
    return '<div class="mode-card"><h3>' + f.mode + ' ' + pill(f.status) +
      '<span class="lbl ' + info.cls + '">' + info.label + '</span></h3>' +
      '<div class="big">+' + f.delay_hours + 'h delay &middot; on-time ' +
      f.on_time_probability + '</div>' +
      '<div class="meta">' + info.sources + ' &middot; updated ' +
      info.updated + '</div></div>';
  }).join("");
  document.getElementById("ranking").innerHTML = demo.ranked_options.map(o =>
    '<div class="opt-card' + (o.rank === 1 ? " top" : "") + '"><strong>#' +
    o.rank + " " + o.option_id + "</strong> &mdash; " + o.title +
    '<div class="nums">score ' + o.score + " &middot; $" + o.cost_usd +
    " &middot; saves " + o.time_saved_hours + "h &middot; on-time " +
    o.on_time_probability + " &middot; confidence " + o.confidence +
    "</div></div>").join("");
}
function gridAskSnapshot(snap) {
  renderDemo(snap);
  document.getElementById("live").textContent =
    "Cards show the asked corridor (" + snap.label + "); use the button for baseline/live views.";
}
async function loadDemo() {
  try {
    renderDemo(await getJSON("/demo/north-sea-storm/live"));
    liveOn = true;
    document.getElementById("live").textContent =
      "Cards show live values; use the button for the storm scenario.";
  } catch (e) {
    renderDemo(await getJSON("/demo/north-sea-storm"));
    document.getElementById("live").textContent =
      "Live fetch failed; showing baseline values.";
  }
}
async function loadSummary() {
  try {
    const demo = await getJSON("/demo/north-sea-storm/summary");
    const s = demo.summary;
    document.getElementById("summary").textContent =
      "[" + s.source + "] " + s.text;
  } catch (e) { document.getElementById("summary").textContent = String(e); }
}
let liveOn = true;
document.getElementById("live-btn").addEventListener("click", async () => {
  const el = document.getElementById("live");
  el.textContent = liveOn ? "Reloading baseline\u2026" : "Fetching live snapshot\u2026";
  try {
    const snap = liveOn ? await getJSON("/demo/north-sea-storm")
      : await getJSON("/demo/north-sea-storm/live");
    renderDemo(snap);
    if (liveOn) { el.textContent = "Cards show the baseline; click again for live values."; }
    else {
    const top = snap.ranked_options[0];
    const sea = snap.findings.find(f => f.mode === "sea");
    el.textContent =
      "waves " + snap.marine.wave_height_m + "m (" + snap.marine.source + ")" +
      ", wind " + snap.wind.wind_kph + "kph (" + snap.wind.source + ")" +
      "; sea " + sea.status + " +" + sea.delay_hours + "h" +
      " [waves " + snap.provenance.sea.wave_height_m +
      ", delay " + snap.provenance.sea.delay_hours + "]" +
      (snap.vessel && snap.vessel.live ? ", " + snap.vessel.vessels_total + " vessels tracked" : "") +
      "; air " + snap.air.source +
      (snap.air.live ? " " + (snap.air.airborne_ams + snap.air.airborne_osl) + " airborne" : "") +
      "; road " + snap.road.source +
      (snap.road.live ? " worst ratio " + snap.road.worst_ratio +
        (snap.road.incidents ? ", " + snap.road.incidents.count +
          " incidents (" + snap.road.incidents.closures + " closures)" : "") +
        (snap.road.route ? ", routed " + snap.road.route.transit_hours + "h" : "")
        : "") +
      "; rail " + snap.rail.source +
      (snap.rail.live ? " " + snap.rail.active_count + " active" : "") +
      "; top pick now " + top.option_id + " at score " + top.score + "." +
      " Cards now show live values; click again for the baseline.";
    }
    liveOn = !liveOn;
  } catch (e) { el.textContent = String(e); }
});
document.getElementById("brief-btn").addEventListener("click", async () => {
  const el = document.getElementById("brief");
  el.textContent = "Asking Muse Wonder\u2026";
  try {
    const demo = await getJSON("/demo/north-sea-storm/brief");
    el.textContent = "[" + demo.brief.source + "] " + demo.brief.text;
  } catch (e) { el.textContent = String(e); }
});
async function checkRunner(model, elId) {
  const el = document.getElementById(elId);
  el.textContent = "Checking runner\u2026";
  try {
    const s = await getJSON("/demo/north-sea-storm/openweights?model=" + model);
    el.textContent = "[" + s.source + "] " + s.label + " (" + s.repo + "). " +
      s.detail + (s.served_models.length ?
        " Served: " + s.served_models.join(", ") + "." : "");
  } catch (e) { el.textContent = String(e); }
}
document.getElementById("ow-spark-btn").addEventListener("click",
  () => checkRunner("spark-open", "ow-spark"));
document.getElementById("ow-glimmer-btn").addEventListener("click",
  () => checkRunner("glimmer", "ow-glimmer"));
async function askRunner(model, elId) {
  const el = document.getElementById(elId);
  el.textContent = "Asking\u2026 local inference can take minutes.";
  try {
    const demo = await getJSON("/demo/north-sea-storm/openweights/ask?model=" + model);
    const o = demo.openweights;
    el.textContent = "[" + o.source + "] " + (o.text || o.detail);
  } catch (e) { el.textContent = String(e); }
}
document.getElementById("ow-ask-spark-btn").addEventListener("click",
  () => askRunner("spark-open", "ow-ask-spark"));
document.getElementById("ow-ask-glimmer-btn").addEventListener("click",
  () => askRunner("glimmer", "ow-ask-glimmer"));
loadDemo().catch(e => { document.getElementById("modes").textContent = String(e); });
loadSummary();
</script>
""" + ask_box.render_ask_script("grid") + """</body>
</html>
"""
