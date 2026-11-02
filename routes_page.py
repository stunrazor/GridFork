"""Route briefing page: dark route-first view of the deterministic demo.

Server-renders hero, KPIs, comparison, schematic, and a deterministic side
brief from ``run_demo()`` with zero live calls. Every live inference (Spark
refresh, SAM, what-if, voice, bench, illustration) runs only on an explicit
click or button hold. Color always pairs with a text label, never alone.
"""

import ask_box
import spark_client

_CSS = """
  :root { color-scheme: dark; }
  body { font-family: -apple-system, "Segoe UI", Verdana, sans-serif;
         margin: 0 auto; max-width: 76rem; padding: 1.5rem 1rem 2rem;
         color: #f4f7fb; background: #0b1526; line-height: 1.45; }
  a { color: #7dd3fc; }
  header.route-head { border-bottom: 2px solid #2a3a55; padding-bottom: 0.75rem; }
  header.route-head h1 { font-size: 1.5rem; margin: 0; }
  header.route-head .sub { color: #c3cede; margin: 0.3rem 0 0; }
  .badge { display: inline-block; font-size: 0.75rem; font-weight: bold;
           padding: 0.1rem 0.5rem; border: 1px solid #7dd3fc; color: #7dd3fc;
           margin-right: 0.35rem; white-space: nowrap; }
  .badge.live { border-color: #7dd3fc; color: #7dd3fc; }
  .badge.warn { border-color: #f5b942; color: #f5b942; }
  .kpi-strip { display: grid; grid-template-columns: repeat(4, 1fr);
               gap: 0.6rem; margin-top: 1rem; }
  .kpi { background: #131f33; border: 1px solid #2a3a55; padding: 0.6rem 0.75rem; }
  .kpi .k { font-size: 0.72rem; color: #c3cede; text-transform: uppercase; }
  .kpi .v { font-size: 1.25rem; font-weight: bold; }
  .hero { background: #131f33; border: 2px solid #7dd3fc;
          padding: 0.9rem 1.1rem; margin-top: 1rem; }
  .hero h2 { margin: 0 0 0.3rem; font-size: 1.15rem; }
  .hero p { margin: 0.3rem 0; }
  .hero .nums { color: #7dd3fc; }
  .main-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 1rem;
               margin-top: 1rem; }
  .panel { background: #131f33; border: 1px solid #2a3a55; padding: 0.75rem 1rem; }
  .panel h2 { font-size: 1.0rem; margin: 0 0 0.5rem;
              border-bottom: 1px solid #2a3a55; padding-bottom: 0.3rem; }
  table { border-collapse: collapse; width: 100%; font-size: 0.85rem; }
  th, td { border: 1px solid #2a3a55; padding: 0.3rem 0.45rem; text-align: left; }
  th { background: #1b2942; color: #c3cede; }
  tr.top td { font-weight: bold; color: #7dd3fc; }
  .pill { display: inline-block; font-size: 0.75rem; font-weight: bold;
          padding: 0.1rem 0.5rem; border: 1px solid #666; }
  .disrupted { background: #b3261e; color: #fff; border-color: #b3261e; }
  .degraded { background: #8a5a00; color: #fff; border-color: #8a5a00; }
  .available { background: #1e7e34; color: #fff; border-color: #1e7e34; }
  .stages { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem;
            margin-top: 1rem; }
  button { font-size: 0.85rem; padding: 0.4rem 0.8rem; cursor: pointer;
           background: #1b2942; color: #f4f7fb; border: 1px solid #7dd3fc; }
  button:active { background: #274067; }
  input { font-size: 0.85rem; padding: 0.35rem 0.5rem; width: 100%;
          max-width: 26rem; background: #0b1526; color: #f4f7fb;
          border: 1px solid #2a3a55; }
  img.illus { max-width: 100%; border: 1px solid #2a3a55; margin-top: 0.5rem; }
  .note { font-size: 0.82rem; color: #c3cede; }
  .label { font-size: 0.82rem; color: #c3cede; border-left: 3px solid #7dd3fc;
           padding-left: 0.6rem; }
  footer { margin-top: 1.5rem; font-size: 0.78rem; color: #c3cede;
           border-top: 1px solid #2a3a55; padding-top: 0.5rem; }
  code { background: #1b2942; padding: 0 0.25rem; }
  svg text { fill: #f4f7fb; font-size: 12px; }
  svg .dim { fill: #c3cede; font-size: 11px; }
  @media (max-width: 60rem) {
    .main-grid { grid-template-columns: 1fr; }
    .stages { grid-template-columns: 1fr; }
    .kpi-strip { grid-template-columns: repeat(2, 1fr); }
  }
"""

_SCRIPT = """
<script>
async function getJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(path + " -> " + r.status);
  return r.json();
}
async function postJSON(path, payload) {
  const r = await fetch(path, {method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)});
  if (!r.ok) throw new Error(path + " -> " + r.status);
  return r.json();
}
const CHALLENGE = "/demo/north-sea-storm/challenge?models=";
document.getElementById("rt-summary-btn").addEventListener("click", async () => {
  const el = document.getElementById("rt-brief");
  el.textContent = "Asking Muse Spark\\u2026";
  try {
    const demo = await getJSON("/demo/north-sea-storm/summary");
    el.textContent = "[" + demo.summary.source + "] " + demo.summary.text;
  } catch (e) { el.textContent = String(e); }
});
document.getElementById("rt-run").addEventListener("click", async () => {
  const el = document.getElementById("rt-result");
  el.textContent = "Asking Muse Wonder\\u2026";
  try {
    const q = document.getElementById("rt-input").value;
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
    const table = document.createElement("table");
    const head2 = document.createElement("tr");
    ["Option", "Rank before \\u2192 after", "Score before \\u2192 after"].forEach(t => {
      const th = document.createElement("th");
      th.textContent = t;
      head2.appendChild(th);
    });
    table.appendChild(head2);
    demo.comparison.forEach(c => {
      const tr = document.createElement("tr");
      [c.option_id, c.rank_before + " \\u2192 " + c.rank_after,
       c.score_before + " \\u2192 " + c.score_after].forEach(v => {
        const td = document.createElement("td");
        td.textContent = v;
        tr.appendChild(td);
      });
      table.appendChild(tr);
    });
    el.appendChild(table);
  } catch (e) { el.textContent = String(e); }
});
let rtRecorder = null, rtChunks = [], rtStopTimer = null;
const rtTalk = document.getElementById("rt-talk");
const rtVoiceStatus = document.getElementById("rt-voice-status");
function rtEncodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  function writeStr(offset, s) {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
  }
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeStr(8, "WAVEfmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }
  return new Blob([buffer], {type: "audio/wav"});
}
async function rtBlobToWav16k(blob) {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  try {
    const audio = await ctx.decodeAudioData(await blob.arrayBuffer());
    const src = audio.getChannelData(0);
    const ratio = audio.sampleRate / 16000;
    const len = Math.floor(src.length / ratio);
    const out = new Float32Array(len);
    for (let i = 0; i < len; i++) out[i] = src[Math.floor(i * ratio)];
    return rtEncodeWav(out, 16000);
  } finally {
    await ctx.close();
  }
}
function rtBlobToB64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(String(reader.result).split(",", 2)[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
rtTalk.addEventListener("pointerdown", async (e) => {
  e.preventDefault();
  if (rtRecorder) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
    rtChunks = [];
    rtRecorder = new MediaRecorder(stream);
    rtRecorder.ondataavailable = (ev) => {
      if (ev.data.size) rtChunks.push(ev.data);
    };
    rtRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      try {
        rtVoiceStatus.textContent = "Voice: transcribing\\u2026";
        const blob = new Blob(rtChunks, {type: rtRecorder.mimeType});
        const wav = await rtBlobToWav16k(blob);
        const b64 = await rtBlobToB64(wav);
        const result = await postJSON("/demo/north-sea-storm/transcribe",
          {audio_b64: b64, filename: "clip.wav"});
        if (result.text) {
          document.getElementById("rt-input").value = result.text;
          rtVoiceStatus.textContent = "[" + result.source + "] transcribed.";
        } else {
          rtVoiceStatus.textContent =
            "[" + result.source + "] " + (result.detail || "no transcript");
        }
      } catch (err) { rtVoiceStatus.textContent = "Voice: " + String(err); }
      rtRecorder = null;
    };
    rtRecorder.start();
    rtVoiceStatus.textContent = "Recording\\u2026 release to transcribe (max 30s).";
    rtStopTimer = setTimeout(() => { if (rtRecorder) rtRecorder.stop(); }, 30000);
  } catch (err) { rtVoiceStatus.textContent = "Microphone unavailable: " + String(err); }
});
function rtEndTalk() {
  if (!rtRecorder) return;
  clearTimeout(rtStopTimer);
  rtRecorder.stop();
}
rtTalk.addEventListener("pointerup", rtEndTalk);
rtTalk.addEventListener("pointerleave", rtEndTalk);
rtTalk.addEventListener("pointercancel", rtEndTalk);
document.getElementById("rt-vision-btn").addEventListener("click", async () => {
  const el = document.getElementById("rt-vision");
  el.textContent = "Running SAM segmentation\\u2026";
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
async function rtChallenge(mock) {
  const el = document.getElementById("rt-challenge");
  el.textContent = "Running comparison\\u2026";
  try {
    const demo = await getJSON(CHALLENGE + "spark-open,glimmer" + (mock ? "&mock=true" : ""));
    el.textContent = "";
    demo.summary.forEach(s => {
      const p = document.createElement("p");
      p.textContent = s.label + ": " + s.agreements + "/" + s.schema_valid +
        " agree (valid " + s.schema_valid + "/" + s.cases + ").";
      el.appendChild(p);
    });
    const table = document.createElement("table");
    const head = document.createElement("tr");
    ["Case", "Model", "Source", "Schema valid", "Agrees"].forEach(t => {
      const th = document.createElement("th");
      th.textContent = t;
      head.appendChild(th);
    });
    table.appendChild(head);
    demo.results.forEach(r => {
      const tr = document.createElement("tr");
      [r.case_id, r.model, r.source, String(r.schema_valid),
       r.agrees_with_ranking === null ? "n/a" : String(r.agrees_with_ranking)
      ].forEach(v => {
        const td = document.createElement("td");
        td.textContent = v;
        tr.appendChild(td);
      });
      table.appendChild(tr);
    });
    el.appendChild(table);
  } catch (e) { el.textContent = String(e); }
}
document.getElementById("rt-live-btn").addEventListener("click", () => rtChallenge(false));
document.getElementById("rt-mock-btn").addEventListener("click", () => rtChallenge(true));
document.getElementById("rt-illus-btn").addEventListener("click", async () => {
  const el = document.getElementById("rt-illustration");
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

_STATUS_FILL = {"disrupted": "#ff6b6b", "degraded": "#f5b942", "available": "#4ade80"}


def _tradeoff_line(ranked_options: list[dict]) -> str:
    """One deterministic sentence on the top pick vs the runner-up."""
    top, runner_up = ranked_options[0], ranked_options[1]
    cost_gap = runner_up["cost_usd"] - top["cost_usd"]
    time_gap = top["time_saved_hours"] - runner_up["time_saved_hours"]
    cost_word = f"saves ${cost_gap}" if cost_gap >= 0 else f"costs ${-cost_gap} more"
    time_word = f"saves {time_gap}h more" if time_gap >= 0 else f"saves {-time_gap}h less"
    return f"Tradeoff vs {runner_up['option_id']}: top pick {cost_word} and {time_word}."


def _schematic(findings: list[dict]) -> str:
    """Code-drawn SVG delay bars: accurate, clearly labeled, never a map."""
    rows = []
    y = 8
    for finding in findings:
        width = max(4, round(finding["delay_hours"] / 48 * 300))
        fill = _STATUS_FILL[finding["status"]]
        rows.append(
            f'<text x="0" y="{y + 12}">{finding["mode"]}</text>'
            f'<rect x="60" y="{y}" width="{width}" height="16" fill="{fill}"/>'
            f'<text class="dim" x="{70 + width}" y="{y + 12}">'
            f'+{finding["delay_hours"]}h {finding["status"]}</text>'
        )
        y += 28
    bars = "".join(rows)
    return (
        f'<svg viewBox="0 0 560 132" width="100%" role="img" '
        f'aria-label="Route status schematic, bar length equals extra delay hours">'
        f"{bars}"
        '<text class="dim" x="60" y="120">bar length = extra delay hours</text>'
        "</svg>"
    )


def render_routes_page(demo: dict) -> str:
    """Return the route briefing as a self-contained HTML document."""
    ranked = demo["ranked_options"]
    top = ranked[0]
    rows = "".join(
        f'<tr class="{"top" if o["rank"] == 1 else ""}"><td>{o["rank"]}</td>'
        f'<td>{o["option_id"]}</td><td>{o["score"]}</td>'
        f'<td>${o["cost_usd"]}</td><td>{o["time_saved_hours"]}h</td>'
        f'<td>{o["on_time_probability"]}</td><td>{o["confidence"]}</td></tr>'
        for o in ranked
    )
    sea = next(f for f in demo["findings"] if f["mode"] == "sea")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>GridFork route briefing &mdash; Rotterdam to Oslo</title>\n<style>"
        + _CSS
        + "</style>\n</head>\n<body>\n"
        '<header class="route-head">\n'
        "<h1>GridFork route briefing &mdash; Rotterdam &rarr; Oslo</h1>\n"
        f'<p class="sub"><span class="pill {sea["status"]}">STORM DISRUPTION</span> '
        '<span class="badge live">LIVE DATA &middot; LABELED ESTIMATES</span> '
        '<span class="badge">DETERMINISTIC SCORING</span> '
        '<a href="/">Home</a></p>\n'
        "</header>\n"
        '<div class="kpi-strip">\n'
        f'<div class="kpi"><div class="k">Score</div><div class="v">{top["score"]}</div></div>\n'
        f'<div class="kpi"><div class="k">Cost</div><div class="v">${top["cost_usd"]}</div></div>\n'
        f'<div class="kpi"><div class="k">Time saved</div><div class="v">{top["time_saved_hours"]}h</div></div>\n'
        f'<div class="kpi"><div class="k">On-time</div><div class="v">{top["on_time_probability"]}</div></div>\n'
        "</div>\n"
        '<div class="hero">\n'
        f'<h2>Recommended: {top["option_id"]} &mdash; {top["title"]}</h2>\n'
        f'<p class="nums">Score {top["score"]} &middot; ${top["cost_usd"]} '
        f'&middot; saves {top["time_saved_hours"]}h '
        f'&middot; on-time {top["on_time_probability"]} '
        f'&middot; confidence {top["confidence"]}</p>\n'
        f"<p>{_tradeoff_line(ranked)}</p>\n"
        "</div>\n"
        '<div class="main-grid">\n'
        '<div class="panel">\n<h2>Route comparison</h2>\n<table>\n'
        "<tr><th>#</th><th>Option</th><th>Score</th><th>Cost</th>"
        "<th>Saved</th><th>On-time</th><th>Conf.</th></tr>\n"
        + rows
        + "</table>\n"
        "<h2>Schematic (not a map)</h2>\n"
        + _schematic(demo["findings"])
        + "</div>\n"
        '<div class="panel">\n<h2>Operations brief</h2>\n'
        f'<p id="rt-brief" class="note">[deterministic] {spark_client.deterministic_summary(ranked)}</p>\n'
        '<button id="rt-summary-btn" type="button">Refresh live (Spark)</button>\n'
        "</div>\n"
        "</div>\n"
        '<div class="stages">\n'
        '<div class="panel">\n<h2>Evidence &mdash; SAM 3.1</h2>\n'
        '<p class="note">Reference imagery, not a live feed. '
        '<span class="badge live">SAM-3.1</span></p>\n'
        '<button id="rt-vision-btn" type="button">Run SAM check</button>\n'
        '<p id="rt-vision" class="note">Not run yet.</p>\n'
        "</div>\n"
        '<div class="panel">\n<h2>What-if &mdash; Wonder + Voice</h2>\n'
        '<p class="note">Assumptions shown; the engine rescores. Hold to talk; '
        "mic only while held. "
        '<span class="badge live">WONDER</span> '
        '<span class="badge live">VOICE</span></p>\n'
        '<input id="rt-input" value="What if Rotterdam closes for six more hours?">\n'
        '<p><button id="rt-run" type="button">Run scenario</button>\n'
        '<button id="rt-talk" type="button">Hold to talk</button></p>\n'
        '<p id="rt-voice-status" class="note">Voice: idle.</p>\n'
        '<div id="rt-result" class="note">Not run yet.</div>\n'
        "</div>\n"
        '<div class="panel">\n<h2>Model Bench &mdash; advisory</h2>\n'
        '<p class="note">Side-by-side open-weight critiques; ranking stays '
        "authoritative. Live needs configured runners; mock uses canned data. "
        '<span class="badge live">SPARK-OPEN</span> '
        '<span class="badge live">GLIMMER</span></p>\n'
        '<p><button id="rt-live-btn" type="button">Run live comparison</button>\n'
        '<button id="rt-mock-btn" type="button">Preview with mock data</button></p>\n'
        '<div id="rt-challenge" class="note">Not run yet.</div>\n'
        "</div>\n"
        '<div class="panel">\n<h2>Visual Brief &mdash; Image</h2>\n'
        '<p class="label">AI-generated editorial illustration &mdash; '
        "illustrative only. Not a real port image, map, or evidence. "
        '<span class="badge warn">AI-GENERATED</span></p>\n'
        '<button id="rt-illus-btn" type="button">Generate illustration</button>\n'
        '<div id="rt-illustration" class="note">Not generated yet.</div>\n'
        "</div>\n"
        '<div class="panel">\n'
        + ask_box.render_ask_box("rt")
        + "</div>\n"
        "</div>\n"
        "<footer>\n<p>Sources: deterministic scoring (always) &middot; brief "
        "summary (Spark live, deterministic offline) &middot; SAM 3.1 "
        "segmentation (live, unavailable offline) &middot; Wonder assumptions "
        "&middot; Voice transcription &middot; open weights (local, "
        "setup-required, or mock) &middot; Muse Image illustration. "
        "Costs and probabilities are synthetic demo data; legs measured with "
        "provenance.</p>\n</footer>\n" + _SCRIPT
        + ask_box.render_ask_script("rt")
        + "</body>\n</html>\n"
    )
