"""Minimal observable grid: one page showing the demo the agents produce.

Plain server-rendered shell plus small fetches to the JSON endpoints. Works
offline (every endpoint falls back deterministically); the SAM verification
block runs on demand so a page load never triggers a live vision call.
"""


def render_grid_page() -> str:
    """Return the full grid page as a self-contained HTML document."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GridFork live grid &mdash; North Sea storm</title>
<style>
  body { font-family: -apple-system, "Segoe UI", Verdana, sans-serif;
         margin: 2rem auto; max-width: 72rem; padding: 0 1rem;
         color: #1a1a1a; background: #fff; line-height: 1.45; }
  h1 { font-size: 1.4rem; margin-bottom: 0; }
  .sub { color: #444; margin-top: 0.25rem; }
  h2 { font-size: 1.05rem; border-bottom: 1px solid #ccc;
       padding-bottom: 0.25rem; margin-top: 2rem; }
  .modes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem; }
  .mode { border: 1px solid #ccc; padding: 0.6rem 0.75rem; }
  .mode h3 { margin: 0 0 0.3rem; font-size: 0.95rem; }
  .pill { display: inline-block; font-size: 0.75rem; font-weight: bold;
          padding: 0.1rem 0.5rem; border: 1px solid #666; }
  .disrupted { background: #f8d7da; }
  .degraded { background: #fff3cd; }
  .available { background: #d4edda; }
  table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
  th, td { border: 1px solid #ccc; padding: 0.35rem 0.5rem; text-align: left; }
  th { background: #eee; }
  tr.top td { font-weight: bold; }
  button { font-size: 0.9rem; padding: 0.4rem 0.9rem; cursor: pointer; }
  .note { font-size: 0.85rem; color: #444; }
  .src { font-size: 0.8rem; color: #444; }
  footer { margin-top: 2rem; font-size: 0.8rem; color: #444;
           border-top: 1px solid #ccc; padding-top: 0.5rem; }
  code { background: #f2f2f2; padding: 0 0.25rem; }
</style>
</head>
<body>
<h1>GridFork live grid &mdash; North Sea storm, Rotterdam &rarr; Oslo</h1>
<p class="sub">Every route. One grid. Zero blind spots. Synthetic demo data.</p>

<h2>Specialist findings</h2>
<div class="modes" id="modes"><p class="note">Loading&hellip;</p></div>

<h2>Ranked reroutes</h2>
<table id="ranking"><tr><td class="note">Loading&hellip;</td></tr></table>

<h2>Narrative summary</h2>
<p id="summary" class="note">Loading&hellip;</p>

<h2>SAM visual verification</h2>
<p class="note">Reference imagery: dense container stacks. Runs on demand.</p>
<button id="vision-btn" type="button">Run SAM verification</button>
<p id="vision" class="note">Not run yet.</p>

<h2>Live wind layer</h2>
<p id="weather" class="note">Loading&hellip;</p>

<footer>
<p>Sources: deterministic scoring (always) &middot; Muse Spark summary
(<code>source: muse-spark</code> live, <code>deterministic</code> offline) &middot;
SAM 3.1 segmentation (<code>source: sam-3.1</code> live,
<code>unavailable</code> offline) &middot; Open-Meteo wind
(<code>live: true</code>) or labeled synthetic fallback.</p>
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
async function loadDemo() {
  const demo = await getJSON("/demo/north-sea-storm");
  document.getElementById("modes").innerHTML = demo.findings.map(f =>
    '<div class="mode"><h3>' + f.mode + ' ' + pill(f.status) + '</h3>' +
    '<div>delay +' + f.delay_hours + 'h &middot; on-time ' +
    f.on_time_probability + '</div></div>').join("");
  const rows = demo.ranked_options.map(o =>
    '<tr class="' + (o.rank === 1 ? "top" : "") + '"><td>' + o.rank +
    '</td><td>' + o.option_id + '</td><td>' + o.score + '</td><td>$' +
    o.cost_usd + '</td><td>' + o.time_saved_hours + 'h</td><td>' +
    o.on_time_probability + '</td><td>' + o.confidence + '</td></tr>').join("");
  document.getElementById("ranking").innerHTML =
    "<tr><th>#</th><th>Option</th><th>Score</th><th>Cost</th>" +
    "<th>Saved</th><th>On-time</th><th>Conf.</th></tr>" + rows;
}
async function loadSummary() {
  try {
    const demo = await getJSON("/demo/north-sea-storm/summary");
    const s = demo.summary;
    document.getElementById("summary").textContent =
      "[" + s.source + "] " + s.text;
  } catch (e) { document.getElementById("summary").textContent = String(e); }
}
async function loadWeather() {
  try {
    const w = await getJSON("/demo/north-sea-storm/weather");
    document.getElementById("weather").textContent =
      (w.live ? "LIVE " : "FALLBACK ") + w.source + ": Rotterdam wind " +
      w.wind_kph + " kph" + (w.observed_at ? " at " + w.observed_at : "");
  } catch (e) { document.getElementById("weather").textContent = String(e); }
}
document.getElementById("vision-btn").addEventListener("click", async () => {
  const el = document.getElementById("vision");
  el.textContent = "Running SAM segmentation\u2026";
  try {
    const demo = await getJSON("/demo/north-sea-storm/vision");
    const v = demo.vision;
    const sea = demo.ranked_options.find(o => o.option_id === "sea-wait");
    el.textContent = "[" + v.source + "] " + v.detections +
      " container detections, congestion " + v.score +
      ", +" + v.sea_delay_added_hours + "h port delay; sea-wait now saves " +
      sea.time_saved_hours + "h at score " + sea.score + ".";
  } catch (e) { el.textContent = String(e); }
});
loadDemo().catch(e => { document.getElementById("modes").textContent = String(e); });
loadSummary();
loadWeather();
</script>
</body>
</html>
"""
