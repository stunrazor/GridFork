"""Shareable incident briefing card: one page summarizing the demo scenario.

Fully deterministic from ``run_demo()`` output; rendering the page never
triggers image generation. The illustration loads on demand from the
existing ``/demo/north-sea-storm/image`` endpoint and is always labeled
illustrative, never evidence — SAM segmentation remains the
vision/evidence step.
"""

import ask_box

_CSS = """
  body { font-family: -apple-system, "Segoe UI", Verdana, sans-serif;
         margin: 2rem auto; max-width: 52rem; padding: 0 1rem;
         color: #1a1a1a; background: #fff; line-height: 1.45; }
  h1 { font-size: 1.4rem; margin-bottom: 0; }
  .sub { color: #444; margin-top: 0.25rem; }
  h2 { font-size: 1.05rem; border-bottom: 1px solid #ccc;
       padding-bottom: 0.25rem; margin-top: 2rem; }
  table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
  th, td { border: 1px solid #ccc; padding: 0.35rem 0.5rem; text-align: left; }
  th { background: #eee; }
  tr.top td { font-weight: bold; }
  .pill { display: inline-block; font-size: 0.75rem; font-weight: bold;
          padding: 0.1rem 0.5rem; border: 1px solid #666; }
  .disrupted { background: #f8d7da; }
  .degraded { background: #fff3cd; }
  .available { background: #d4edda; }
  .rec { border: 2px solid #1a1a1a; padding: 0.75rem 1rem; }
  .rec p { margin: 0.3rem 0; }
  button { font-size: 0.9rem; padding: 0.4rem 0.9rem; cursor: pointer; }
  img.illus { max-width: 100%; border: 1px solid #ccc; margin-top: 0.5rem; }
  .note { font-size: 0.85rem; color: #444; }
  .label { font-size: 0.85rem; color: #444; border-left: 3px solid #666;
           padding-left: 0.6rem; }
  footer { margin-top: 2rem; font-size: 0.8rem; color: #444;
           border-top: 1px solid #ccc; padding-top: 0.5rem; }
  code { background: #f2f2f2; padding: 0 0.25rem; }
  @media print { button, input { display: none; } }
"""

_SCRIPT = """
<script>
async function getJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(path + " -> " + r.status);
  return r.json();
}
document.getElementById("illus-btn").addEventListener("click", async () => {
  const el = document.getElementById("illustration");
  el.textContent = "Generating illustration\\u2026";
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
</script>
"""


def _tradeoff_line(ranked_options: list[dict]) -> str:
    """One deterministic sentence on the top pick vs the runner-up."""
    top, runner_up = ranked_options[0], ranked_options[1]
    cost_gap = runner_up["cost_usd"] - top["cost_usd"]
    time_gap = top["time_saved_hours"] - runner_up["time_saved_hours"]
    cost_word = f"saves ${cost_gap}" if cost_gap >= 0 else f"costs ${-cost_gap} more"
    time_word = f"saves {time_gap}h more" if time_gap >= 0 else f"saves {-time_gap}h less"
    return f"Tradeoff vs {runner_up['option_id']}: top pick {cost_word} and {time_word}."


def render_brief_card(demo: dict) -> str:
    """Return the incident brief as a self-contained HTML document."""
    top = demo["ranked_options"][0]
    findings_rows = "".join(
        f'<tr><td>{f["mode"]}</td>'
        f'<td><span class="pill {f["status"]}">{f["status"]}</span></td>'
        f'<td>+{f["delay_hours"]}h</td>'
        f'<td>{f["on_time_probability"]}</td></tr>'
        for f in demo["findings"]
    )
    ranking_rows = "".join(
        f'<tr class="{"top" if o["rank"] == 1 else ""}"><td>{o["rank"]}</td>'
        f'<td>{o["option_id"]}</td><td>{o["score"]}</td>'
        f'<td>${o["cost_usd"]}</td><td>{o["time_saved_hours"]}h</td>'
        f'<td>{o["on_time_probability"]}</td><td>{o["confidence"]}</td></tr>'
        for o in demo["ranked_options"]
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>GridFork incident brief &mdash; North Sea storm</title>\n<style>"
        + _CSS
        + "</style>\n</head>\n<body>\n"
        "<h1>GridFork incident brief &mdash; North Sea storm, Rotterdam &rarr; Oslo</h1>\n"
        f'<p class="sub">Every route. One grid. Zero blind spots. {demo["label"]} '
        '<a href="/">Home</a>.</p>\n'
        '<p class="note">Shareable page: print to PDF to distribute.</p>\n'
        + ask_box.render_ask_box("brief")
        + "<h2>Recommendation</h2>\n"
        '<div class="rec">\n'
        f'<p><strong>{top["option_id"]}</strong> &mdash; {top["title"]}</p>\n'
        f'<p>Score {top["score"]} &middot; ${top["cost_usd"]} '
        f'&middot; saves {top["time_saved_hours"]}h '
        f'&middot; on-time {top["on_time_probability"]} '
        f'&middot; confidence {top["confidence"]}</p>\n'
        f"<p>{_tradeoff_line(demo['ranked_options'])}</p>\n"
        "</div>\n"
        "<h2>Impacts</h2>\n<table>\n"
        "<tr><th>Mode</th><th>Status</th><th>Delay</th><th>On-time</th></tr>\n"
        + findings_rows
        + "</table>\n"
        "<h2>Ranking</h2>\n<table>\n"
        "<tr><th>#</th><th>Option</th><th>Score</th><th>Cost</th>"
        "<th>Saved</th><th>On-time</th><th>Conf.</th></tr>\n"
        + ranking_rows
        + "</table>\n"
        "<h2>Illustration</h2>\n"
        '<p class="label">AI-generated illustration (Muse Image) &mdash; '
        "illustrative only. Not a real port image, map, or evidence. "
        "Vision evidence comes from SAM 3.1 segmentation of reference "
        "imagery.</p>\n"
        '<button id="illus-btn" type="button">Generate illustration</button>\n'
        '<div id="illustration" class="note">Not generated yet. Paid Muse Image '
        "call; runs on demand only.</div>\n"
        "<footer>\n<p>Sources: deterministic scoring (always) &middot; "
        "illustration via <code>/demo/north-sea-storm/image</code> "
        "(<code>source: muse-image</code> live, "
        "<code>unavailable</code> offline) &middot; SAM 3.1 segmentation is "
        "the vision/evidence step. Costs and probabilities are synthetic "
        "estimates.</p>\n</footer>\n"
        + _SCRIPT
        + ask_box.render_ask_script("brief")
        + "</body>\n</html>\n"
    )
