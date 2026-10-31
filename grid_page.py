"""Minimal observable grid: one page showing the demo the agents produce.

Plain server-rendered shell plus small fetches to the JSON endpoints. Works
offline (every endpoint falls back deterministically); the SAM verification
block and the Meta Models section run on demand so a page load never
triggers a live vision, Wonder, Image, or runner call.
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
  input { font-size: 0.9rem; padding: 0.35rem 0.5rem; width: 65%; }
  h3 { font-size: 0.95rem; margin: 1.25rem 0 0.25rem; }
  img.illus { max-width: 100%; border: 1px solid #ccc; margin-top: 0.5rem; }
  .note { font-size: 0.85rem; color: #444; }
  .src { font-size: 0.8rem; color: #444; }
  footer { margin-top: 2rem; font-size: 0.8rem; color: #444;
           border-top: 1px solid #ccc; padding-top: 0.5rem; }
  code { background: #f2f2f2; padding: 0 0.25rem; }
</style>
</head>
<body>
<h1>GridFork live grid &mdash; North Sea storm, Rotterdam &rarr; Oslo</h1>
<p class="sub">Every route. One grid. Zero blind spots. Synthetic demo data.
Open the <a href="/demo/north-sea-storm/brief-card">shareable incident brief</a>,
the <a href="/demo/storm-lab">Storm Scenario Lab</a>, the
<a href="/demo/routes">route briefing</a>, or <a href="/">home</a>.</p>

<h2>Specialist findings</h2>
<div class="modes" id="modes"><p class="note">Loading&hellip;</p></div>

<h2>Ranked reroutes</h2>
<table id="ranking"><tr><td class="note">Loading&hellip;</td></tr></table>

<h2>What-if planner</h2>
<p class="note">Ask Muse Wonder to turn a question into explicit assumptions;
the deterministic engine recomputes the ranking. Runs on demand.</p>
<input id="whatif-input" value="What if Rotterdam closes for six more hours?">
<button id="whatif-btn" type="button">Run what-if</button>
<div id="whatif" class="note">Not run yet.</div>

<h2>Narrative summary</h2>
<p id="summary" class="note">Loading&hellip;</p>

<h2>SAM visual verification</h2>
<p class="note">Reference imagery: dense container stacks. Runs on demand.</p>
<button id="vision-btn" type="button">Run SAM verification</button>
<p id="vision" class="note">Not run yet.</p>

<h2>Live wind layer</h2>
<p id="weather" class="note">Loading&hellip;</p>

<h2>Meta Models (optional)</h2>
<p class="note">On-demand extras. Nothing here runs on page load. Wonder and
Image are paid Meta API calls; open weights need a local runner.</p>
<h3>Muse Wonder &mdash; decision explanation</h3>
<p class="note">Grounded in the current findings and ranking.</p>
<button id="brief-btn" type="button">Explain this scenario</button>
<p id="brief" class="note">Not run yet.</p>
<h3>Muse Image &mdash; illustration</h3>
<p class="note">AI-generated port/storm illustration. Separate from SAM
segmentation, which measures real imagery.</p>
<button id="image-btn" type="button">Generate port image</button>
<div id="illustration" class="note">Not run yet.</div>
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
<h3>Route challenge &mdash; both models critique the ranking</h3>
<p class="note">Advisory only: the deterministic ranking stays authoritative.
Same three storm cases per model; shows agreement, schema validity, latency,
and tokens. Runs on demand; local inference can take minutes.</p>
<button id="challenge-btn" type="button">Run route challenge</button>
<div id="challenge" class="note">Not run yet.</div>

<footer>
<p>Sources: deterministic scoring (always) &middot; Muse Spark summary
(<code>source: muse-spark</code> live, <code>deterministic</code> offline) &middot;
SAM 3.1 segmentation (<code>source: sam-3.1</code> live,
<code>unavailable</code> offline) &middot; Open-Meteo wind
(<code>live: true</code>) or labeled synthetic fallback &middot; Muse Wonder
brief (<code>muse-wonder</code> live, <code>deterministic</code> offline)
&middot; Muse Image illustration (<code>muse-image</code> live,
<code>unavailable</code> offline) &middot; open weights
(<code>setup-required</code> until a runner is configured) &middot; what-if
planner (Wonder assumptions, deterministic rescoring) &middot; route
challenge (advisory critiques, ranking authoritative).</p>
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
document.getElementById("brief-btn").addEventListener("click", async () => {
  const el = document.getElementById("brief");
  el.textContent = "Asking Muse Wonder\u2026";
  try {
    const demo = await getJSON("/demo/north-sea-storm/brief");
    el.textContent = "[" + demo.brief.source + "] " + demo.brief.text;
  } catch (e) { el.textContent = String(e); }
});
document.getElementById("whatif-btn").addEventListener("click", async () => {
  const el = document.getElementById("whatif");
  el.textContent = "Asking Muse Wonder\u2026";
  try {
    const q = document.getElementById("whatif-input").value;
    const demo = await getJSON("/demo/north-sea-storm/whatif?q=" + encodeURIComponent(q));
    el.textContent = "";
    const head = document.createElement("p");
    head.textContent = "[" + demo.whatif.source + "] " + demo.whatif.explanation;
    el.appendChild(head);
    const list = document.createElement("ul");
    if (demo.whatif.assumptions.length === 0) {
      const li = document.createElement("li");
      li.textContent = "No assumptions: ranking unchanged.";
      list.appendChild(li);
    }
    demo.whatif.assumptions.forEach(a => {
      const li = document.createElement("li");
      li.textContent = a.mode + " " + a.field + " " +
        (a.delta > 0 ? "+" : "") + a.delta + (a.reason ? " (" + a.reason + ")" : "");
      list.appendChild(li);
    });
    el.appendChild(list);
    const rows = demo.comparison.map(c =>
      "<tr><td>" + c.option_id + "</td><td>" + c.rank_before + " &rarr; " +
      c.rank_after + "</td><td>" + c.score_before + " &rarr; " +
      c.score_after + "</td></tr>").join("");
    const table = document.createElement("table");
    table.innerHTML = "<tr><th>Option</th><th>Rank before &rarr; after</th>" +
      "<th>Score before &rarr; after</th></tr>" + rows;
    el.appendChild(table);
  } catch (e) { el.textContent = String(e); }
});
document.getElementById("image-btn").addEventListener("click", async () => {
  const el = document.getElementById("illustration");
  el.textContent = "Generating illustration\u2026";
  try {
    const demo = await getJSON("/demo/north-sea-storm/image");
    const img = demo.image;
    if (img.data_url) {
      el.textContent = "[" + img.source + "] " + img.note + " ";
      const tag = document.createElement("img");
      tag.src = img.data_url;
      tag.alt = "AI-generated port illustration";
      tag.className = "illus";
      el.appendChild(tag);
    } else {
      el.textContent = "[" + img.source + "] " + img.note;
    }
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
document.getElementById("challenge-btn").addEventListener("click", async () => {
  const el = document.getElementById("challenge");
  el.textContent = "Running route challenge\u2026 this can take minutes.";
  try {
    const demo = await getJSON("/demo/north-sea-storm/challenge?models=spark-open,glimmer");
    el.textContent = "";
    demo.summary.forEach(s => {
      const p = document.createElement("p");
      p.textContent = s.label + ": " + s.agreements + "/" + s.schema_valid +
        " agree with the ranking (valid " + s.schema_valid + "/" + s.cases +
        "), " + (s.total_tokens === null ? "tokens n/a" : s.total_tokens +
        " tokens") + ", " + (s.avg_latency_ms === null ? "latency n/a" :
        "avg " + s.avg_latency_ms + " ms") + ".";
      el.appendChild(p);
    });
    const table = document.createElement("table");
    const head = document.createElement("tr");
    ["Case", "Model", "Schema valid", "Agrees", "Latency ms", "Tokens"].forEach(t => {
      const th = document.createElement("th");
      th.textContent = t;
      head.appendChild(th);
    });
    table.appendChild(head);
    demo.results.forEach(r => {
      const tr = document.createElement("tr");
      const tokens = (r.usage && r.usage.total_tokens !== null &&
        r.usage.total_tokens !== undefined) ? String(r.usage.total_tokens) : "n/a";
      [r.case_id, r.model, String(r.schema_valid),
       r.agrees_with_ranking === null ? "n/a" : String(r.agrees_with_ranking),
       r.latency_ms === null ? "n/a" : String(r.latency_ms), tokens].forEach(v => {
        const td = document.createElement("td");
        td.textContent = v;
        tr.appendChild(td);
      });
      table.appendChild(tr);
    });
    el.appendChild(table);
  } catch (e) { el.textContent = String(e); }
});
loadDemo().catch(e => { document.getElementById("modes").textContent = String(e); });
loadSummary();
loadWeather();
</script>
</body>
</html>
"""
