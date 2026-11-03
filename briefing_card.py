"""Shareable incident briefing card: one page summarizing the demo scenario.

Fully deterministic from ``run_demo()`` output; the live values refresh
on open and on click. Scenario tools (what-if, evidence, bench,
illustration) live in the route briefing.
"""

import ask_box

_CSS = """
  :root { color-scheme: dark; }
  body { font-family: -apple-system, "Segoe UI", Verdana, sans-serif;
         margin: 2rem auto; max-width: 52rem; padding: 0 1rem;
         color: #f4f7fb; background: #0b1526; line-height: 1.45; }
  a { color: #7dd3fc; }
  h1 { font-size: 1.4rem; margin-bottom: 0; }
  .sub { color: #c3cede; margin-top: 0.25rem; }
  h2 { font-size: 1.05rem; border-bottom: 1px solid #2a3a55;
       padding-bottom: 0.25rem; margin-top: 2rem; }
  table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
  th, td { border: 1px solid #2a3a55; padding: 0.35rem 0.5rem; text-align: left; }
  th { background: #1b2942; color: #c3cede; }
  tr.top td { font-weight: bold; color: #7dd3fc; }
  .pill { display: inline-block; font-size: 0.75rem; font-weight: bold;
          padding: 0.1rem 0.5rem; border: 1px solid #666; }
  .disrupted { background: #b3261e; color: #fff; border-color: #b3261e; }
  .degraded { background: #8a5a00; color: #fff; border-color: #8a5a00; }
  .available { background: #1e7e34; color: #fff; border-color: #1e7e34; }
  .rec { background: #131f33; border: 2px solid #7dd3fc; padding: 0.75rem 1rem; }
  .rec p { margin: 0.3rem 0; }
  button { font-size: 0.9rem; padding: 0.4rem 0.9rem; cursor: pointer;
           background: #1b2942; color: #f4f7fb; border: 1px solid #7dd3fc; }
  button:active { background: #274067; }
  input { font-size: 0.9rem; padding: 0.35rem 0.5rem; width: 65%;
          background: #0b1526; color: #f4f7fb; border: 1px solid #2a3a55; }
  .note { font-size: 0.85rem; color: #c3cede; }
  ul.note { padding-left: 1.2rem; }
  ul.note li { margin: 0.2rem 0; }
  .ask-out { background: #131f33; border: 1px solid #2a3a55;
             padding: 0.6rem 0.8rem; margin-top: 0.5rem; min-height: 2.5rem;
             font-size: 0.9rem; }
  footer { margin-top: 2rem; font-size: 0.8rem; color: #c3cede;
           border-top: 1px solid #2a3a55; padding-top: 0.5rem; }
  code { background: #1b2942; padding: 0 0.25rem; }
  @media (max-width: 40rem) {
    body { font-size: 1.06rem; }
    .note, .sub, footer { font-size: 0.95rem; }
    button, input, table { font-size: 1rem; }
    th, td { padding: 0.45rem 0.6rem; }
    table { display: block; overflow-x: auto; }
  }
  @media print {
    button, input { display: none; }
    body { background: #fff; color: #000; }
    .sub, .note, footer { color: #333; }
    th { background: #eee; color: #000; }
    th, td { border-color: #999; }
    .rec, .ask-out { background: #fff; border-color: #000; }
  }
"""

_SCRIPT = """
<script>
async function getJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(path + " -> " + r.status);
  return r.json();
}
async function briefLoadLive() {
  const el = document.getElementById("brief-live-note");
  el.textContent = "Fetching live snapshot…";
  try {
    briefAskSnapshot(await getJSON("/demo/north-sea-storm/live"));
    el.textContent = "Showing live measured values.";
  } catch (e) { el.textContent = "Live fetch failed (" + e + "); showing baseline values."; }
}
function briefAskSnapshot(snap) {
  const el = document.getElementById("brief-live-note");
  const top = snap.ranked_options[0];
  const run = snap.ranked_options[1];
  document.getElementById("brief-rec-title").textContent =
      top.option_id + " — " + top.title;
    document.getElementById("brief-rec-nums").textContent =
      "Score " + top.score + " · $" + top.cost_usd +
      " · saves " + top.time_saved_hours + "h" +
      " · on-time " + top.on_time_probability +
      " · confidence " + top.confidence;
    const costGap = run.cost_usd - top.cost_usd;
    const timeGap = top.time_saved_hours - run.time_saved_hours;
    document.getElementById("brief-tradeoff").textContent =
      "Tradeoff vs " + run.option_id + ": top pick " +
      (costGap >= 0 ? "saves $" + costGap : "costs $" + (-costGap) + " more") +
      " and " + (timeGap >= 0 ? "saves " + timeGap + "h more" : "saves " + (-timeGap) + "h less") + ".";
    const fa = snap.fastest_alternative;
    document.getElementById("brief-fastest").textContent =
      "Fastest: " + fa.option_id + " (" + fa.total_hours + "h total)";
    document.getElementById("brief-alts").textContent =
      "Alternatives, in order: " +
      snap.ranked_options.slice(1).map(o => o.option_id).join(", ") + ".";
    document.getElementById("brief-captured").textContent =
      "Brief captured: " + new Date().toLocaleString() + " (" + snap.label + ").";
    const src = (l) => (l && l.source) || "reference incident";
    document.getElementById("brief-sources").textContent =
      "sea: " + src(snap.marine) + " / " + src(snap.wind) +
      "; air: " + src(snap.air) + "; road: " + src(snap.road) +
      "; rail: " + src(snap.rail) + ".";
    const impacts = document.getElementById("brief-findings-body");
    impacts.textContent = "";
    snap.findings.forEach(f => {
      const tr = document.createElement("tr");
      const pill = document.createElement("span");
      pill.className = "pill " + f.status;
      pill.textContent = f.status;
      const tds = [f.mode, null, "+" + f.delay_hours + "h", f.on_time_probability];
      tds.forEach(v => {
        const td = document.createElement("td");
        if (v === null) td.appendChild(pill);
        else td.textContent = v;
        tr.appendChild(td);
      });
      impacts.appendChild(tr);
    });
    const body = document.getElementById("brief-ranking-body");
    body.textContent = "";
    snap.ranked_options.forEach(o => {
      const tr = document.createElement("tr");
      if (o.rank === 1) tr.className = "top";
      [o.rank, o.option_id, o.score, "$" + o.cost_usd,
       o.time_saved_hours + "h", o.on_time_probability, o.confidence].forEach(v => {
        const td = document.createElement("td");
        td.textContent = v;
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
    el.textContent = "Tables show the asked corridor (" + snap.label + ").";
}
document.getElementById("brief-live-btn").addEventListener("click", briefLoadLive);
briefLoadLive();
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
        "<title>GridFork incident brief</title>\n<style>"
        + _CSS
        + "</style>\n</head>\n<body>\n"
        "<h1>GridFork incident brief</h1>\n"
        '<p class="sub">Multi-agent reroute engine across sea, air, road and rail. '
        '<a href="/">Home</a>.</p>\n'
        '<p class="note">Shareable page: print to PDF to distribute.</p>\n'
        + ask_box.render_ask_box("brief")
        + "<h2>Recommendation</h2>\n"
        '<p><button id="brief-live-btn" type="button">Refresh live values</button>\n'
        '<span id="brief-live-note" class="note">Loading live values…</span></p>\n'
        '<p id="brief-captured" class="note">Brief captured: —</p>\n'
        '<div class="rec">\n'
        f'<p id="brief-rec-title"><strong>{top["option_id"]}</strong> &mdash; {top["title"]}</p>\n'
        f'<p id="brief-rec-nums">Score {top["score"]} &middot; ${top["cost_usd"]} '
        f'&middot; saves {top["time_saved_hours"]}h '
        f'&middot; on-time {top["on_time_probability"]} '
        f'&middot; confidence {top["confidence"]}</p>\n'
        f'<p id="brief-fastest">Fastest: {demo["fastest_alternative"]["option_id"]} '
        f'({demo["fastest_alternative"]["total_hours"]}h total)</p>\n'
        f"<p id=\"brief-tradeoff\">{_tradeoff_line(demo['ranked_options'])}</p>\n"
        f'<p id="brief-alts">Alternatives, in order: '
        f'{", ".join(o["option_id"] for o in demo["ranked_options"][1:])}.</p>\n'
        "</div>\n"
        "<h2>Impacts</h2>\n<table>\n"
        "<tr><th>Mode</th><th>Status</th><th>Delay</th><th>On-time</th></tr>\n"
        '<tbody id="brief-findings-body">\n'
        + findings_rows
        + "</tbody>\n</table>\n"
        "<h2>Ranking</h2>\n<table>\n"
        "<tr><th>#</th><th>Option</th><th>Score</th><th>Cost</th>"
        "<th>Saved</th><th>On-time</th><th>Conf.</th></tr>\n"
        '<tbody id="brief-ranking-body">\n'
        + ranking_rows
        + "</tbody>\n</table>\n"
        "<h2>Evidence sources</h2>\n"
        '<p id="brief-sources" class="note">reference incident</p>\n'
        "<h2>Assumptions</h2>\n"
        '<ul class="note">\n'
        "<li>Costs, on-time odds, and confidence are modeled estimates, "
        "not quotes or measurements.</li>\n"
        "<li>Delays follow documented rules from measured conditions "
        "where feeds reach; otherwise estimated defaults.</li>\n"
        "<li>Transit legs assume standard freight speeds and handling; "
        "no booking, capacity, or customs checks.</li>\n"
        "</ul>\n"
        "<h2>How to read the numbers</h2>\n"
        '<ul class="note">\n'
        "<li>Delay hours: measured where a feed covers the leg, "
        "estimated otherwise.</li>\n"
        "<li>Cost, on-time, confidence: always estimates.</li>\n"
        "<li>Status: available, degraded, or disrupted per leg.</li>\n"
        "</ul>\n"
        "<footer>\n<p>Sources: deterministic scoring (always) &middot; "
        "live measured legs with provenance &middot; Ask GridFork "
        "(Spark/Wonder routing, paid, click only). Costs and probabilities "
        "are estimates. Scenario tools live in the route briefing.</p>\n</footer>\n"
        + _SCRIPT
        + ask_box.render_ask_script("brief")
        + "</body>\n</html>\n"
    )
