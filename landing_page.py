"""GridFork landing page: what needs attention, then shortcuts.

The shell is static; one small fetch loads the live incident snapshot for
the attention panel. Each card links to one demo view; every view links
back here.
"""

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GridFork &mdash; multi-agent reroute engine</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: -apple-system, "Segoe UI", Verdana, sans-serif;
         margin: 0 auto; max-width: 60rem; padding: 2rem 1rem;
         color: #f4f7fb; background: #0b1526; line-height: 1.45; }
  a { color: #7dd3fc; }
  h1 { font-size: 1.6rem; margin-bottom: 0; }
  .sub { color: #c3cede; margin-top: 0.3rem; }
  .badge { display: inline-block; font-size: 0.75rem; font-weight: bold;
           padding: 0.1rem 0.5rem; border: 1px solid #7dd3fc; color: #7dd3fc;
           margin-right: 0.35rem; white-space: nowrap; }
  .attention { background: #131f33; border: 2px solid #7dd3fc;
              padding: 0.9rem 1.1rem; margin-top: 1.25rem; }
  .attention h2 { margin: 0 0 0.3rem; font-size: 1.15rem; }
  .attention p { margin: 0.3rem 0; }
  .attention .dim { color: #c3cede; font-size: 0.9rem; }
  .cta { display: inline-block; font-size: 1.05rem; font-weight: bold;
         padding: 0.6rem 1.4rem; margin-top: 1rem;
         background: #1b2942; color: #f4f7fb; border: 2px solid #7dd3fc;
         text-decoration: none; }
  .cta:active { background: #274067; }
  .cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;
           margin-top: 1.5rem; }
  .card { background: #131f33; border: 1px solid #2a3a55; padding: 1rem 1.1rem; }
  .card h2 { margin: 0 0 0.3rem; font-size: 1.05rem; }
  .card p { margin: 0.3rem 0 0.8rem; color: #c3cede; font-size: 0.9rem; }
  .card a.btn { display: inline-block; font-size: 0.9rem; padding: 0.45rem 1rem;
                background: #1b2942; color: #f4f7fb; border: 1px solid #7dd3fc;
                text-decoration: none; }
  .card a.btn:active { background: #274067; }
  footer { margin-top: 1.5rem; font-size: 0.78rem; color: #c3cede;
           border-top: 1px solid #2a3a55; padding-top: 0.5rem; }
  @media (max-width: 45rem) { .cards { grid-template-columns: 1fr; } }
  @media (max-width: 40rem) {
    body { font-size: 1.06rem; }
    .card p, .attention .dim, footer { font-size: 0.95rem; }
    .card a.btn, .cta { font-size: 1rem; }
  }
</style>
</head>
<body>
<h1>GridFork</h1>
<p class="sub">Multi-agent reroute engine: live traffic, weather &amp;
disruption data across sea, air, road and rail, scored by cost, time
saved and on-time odds.
<span class="badge">LIVE DATA &middot; LABELED ESTIMATES</span></p>

<div class="attention" id="attention">
<h2>What needs attention?</h2>
<p class="dim">Loading live incident snapshot…</p>
</div>
<a class="cta" href="/demo/routes">Open route briefing</a>

<div class="cards">
<div class="card">
<h2>Live grid</h2>
<p>Four mode cards with live condition, source, and freshness. The
monitoring seat; scenario tools live in the briefing.</p>
<a class="btn" href="/demo/grid">Open live grid</a>
</div>
<div class="card">
<h2>Scenario lab</h2>
<p>Corridor picker with Ask grounded in your pick, plus a
single-assumption what-if with before/after comparison.</p>
<a class="btn" href="/demo/storm-lab">Open scenario lab</a>
</div>
<div class="card">
<h2>Incident brief</h2>
<p>Shareable one-page brief: recommendation, impacts, ranked reroutes.
Deterministic and print-friendly.</p>
<a class="btn" href="/demo/north-sea-storm/brief-card">Open incident brief</a>
</div>
</div>

<footer>
<p>Ask GridFork tops every view. All live inference runs on demand only &mdash;
nothing calls a model on page load. Costs and probabilities stay estimates; legs measured live.</p>
</footer>
<script>
async function loadAttention() {
  const el = document.getElementById("attention");
  try {
    const r = await fetch("/demo/north-sea-storm/live");
    if (!r.ok) throw new Error("live -> " + r.status);
    const snap = await r.json();
    const rank = {disrupted: 0, degraded: 1, available: 2};
    const worst = snap.findings.slice().sort((a, b) =>
      (rank[a.status] - rank[b.status]) || (b.delay_hours - a.delay_hours))[0];
    const src = {
      sea: snap.marine.source + "/" + snap.wind.source,
      air: snap.air.source, road: snap.road.source, rail: snap.rail.source
    };
    const stamps = [snap.marine, snap.wind, snap.air, snap.road, snap.rail]
      .map(l => l.observed_at).filter(Boolean).sort();
    el.textContent = "";
    const head = document.createElement("h2");
    head.textContent = "What needs attention?";
    el.appendChild(head);
    const seaLabel = worst.mode === "sea" ? " (North Sea)" : "";
    const lines = [
      "Corridor: " + snap.label + ".",
      "Attention: " + worst.mode + seaLabel + " " + worst.status +
        " (+" + worst.delay_hours + "h) [" + src[worst.mode] + "].",
      stamps.length ? "Data as of " + stamps[stamps.length - 1] + "." :
        "Live data pending; estimates shown."
    ];
    try {
      const vr = await fetch("/vessels");
      if (vr.ok) {
        const vessels = await vr.json();
        const labels = {hormuz: "Strait of Hormuz",
          dover: "English Channel", suez: "Suez Canal"};
        if (vessels.live) {
          ["hormuz", "dover", "suez"].forEach(tag => {
            lines.push("Sea traffic, " + labels[tag] + ": " +
              vessels["vessels_" + tag] + " vessels tracked [" +
              vessels.source + "].");
          });
        } else if (vessels.source === "setup-required") {
          lines.push("Sea traffic: vessel counts unavailable " +
            "(AIS key not configured).");
        } else {
          lines.push("Sea traffic: vessel counts unavailable [" +
            vessels.source + "].");
        }
      }
    } catch (ignored) { /* incident lines still render */ }
    lines.forEach((t, i) => {
      const p = document.createElement("p");
      if (i > 0) p.className = "dim";
      p.textContent = t;
      el.appendChild(p);
    });
  } catch (e) {
    el.textContent = "";
    const head = document.createElement("h2");
    head.textContent = "What needs attention?";
    el.appendChild(head);
    const p = document.createElement("p");
    p.className = "dim";
    p.textContent = "Live snapshot unreachable; open the Route Briefing " +
      "for the baseline incident view.";
    el.appendChild(p);
  }
}
loadAttention();
</script>
</body>
</html>
"""


def render_landing() -> str:
    """Return the landing page as a self-contained HTML document."""
    return _PAGE