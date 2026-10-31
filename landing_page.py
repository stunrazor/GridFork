"""GridFork landing page: one home with buttons to every view.

Fully static: no live calls of any kind. Each card links to one demo view;
every view links back here.
"""

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GridFork &mdash; every route, one grid</title>
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
  .cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem;
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
</style>
</head>
<body>
<h1>GridFork</h1>
<p class="sub">Every route. One grid. Zero blind spots.
<span class="badge">SYNTHETIC DEMO DATA</span></p>

<div class="cards">
<div class="card">
<h2>Route briefing <span class="badge">NEWEST</span></h2>
<p>Hero recommendation, KPIs, route comparison with a data-drawn schematic,
and Evidence / What-if / Bench / Visual stages.</p>
<a class="btn" href="/demo/routes">Open route briefing</a>
</div>
<div class="card">
<h2>Live grid</h2>
<p>The observable demo interface: specialist findings, ranked reroutes,
Spark summary, SAM check, and live wind.</p>
<a class="btn" href="/demo/grid">Open live grid</a>
</div>
<div class="card">
<h2>Storm Scenario Lab</h2>
<p>Workbench: typed or push-to-talk what-if input, open-weight comparison
with mock preview, on-demand illustration.</p>
<a class="btn" href="/demo/storm-lab">Open scenario lab</a>
</div>
<div class="card">
<h2>Incident brief</h2>
<p>Shareable one-page brief: recommendation, impacts, ranking, and an
optional AI-generated illustration. Print-friendly.</p>
<a class="btn" href="/demo/north-sea-storm/brief-card">Open incident brief</a>
</div>
</div>

<footer>
<p>All live inference across these views runs on demand only &mdash; nothing
calls a model on page load. Synthetic demo data throughout.</p>
</footer>
</body>
</html>
"""


def render_landing() -> str:
    """Return the landing page as a self-contained HTML document."""
    return _PAGE
