"""Storm Scenario Lab: optional workbench beside the GridFork demo.

Fully client-driven: the page renders instantly with no live calls, and every
inference (what-if, transcription, comparison, illustration) runs only on an
explicit click or button hold. The microphone is used only while the
push-to-talk button is held; nothing is recorded automatically.
"""

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GridFork Storm Scenario Lab</title>
<style>
  body { font-family: -apple-system, "Segoe UI", Verdana, sans-serif;
         margin: 2rem auto; max-width: 72rem; padding: 0 1rem;
         color: #1a1a1a; background: #fff; line-height: 1.45; }
  h1 { font-size: 1.4rem; margin-bottom: 0; }
  .sub { color: #444; margin-top: 0.25rem; }
  h2 { font-size: 1.05rem; border-bottom: 1px solid #ccc;
       padding-bottom: 0.25rem; margin-top: 2rem; }
  table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
  th, td { border: 1px solid #ccc; padding: 0.35rem 0.5rem; text-align: left; }
  th { background: #eee; }
  button { font-size: 0.9rem; padding: 0.4rem 0.9rem; cursor: pointer; }
  input { font-size: 0.9rem; padding: 0.35rem 0.5rem; width: 60%; }
  img.illus { max-width: 100%; border: 1px solid #ccc; margin-top: 0.5rem; }
  .note { font-size: 0.85rem; color: #444; }
  .label { font-size: 0.85rem; color: #444; border-left: 3px solid #666;
           padding-left: 0.6rem; }
  footer { margin-top: 2rem; font-size: 0.8rem; color: #444;
           border-top: 1px solid #ccc; padding-top: 0.5rem; }
  code { background: #f2f2f2; padding: 0 0.25rem; }
</style>
</head>
<body>
<h1>Storm Scenario Lab</h1>
<p class="sub">Optional workbench beside the live grid. Synthetic demo data.
Every live call below runs only when you click. <a href="/demo/grid">Back to
the grid</a>.</p>

<h2>1. Scenario question</h2>
<p class="note">Type a what-if, or hold the talk button to dictate it. The
microphone is used only while you hold the button; nothing is recorded
automatically.</p>
<input id="lab-input" value="What if Rotterdam closes for six more hours?">
<button id="lab-run" type="button">Run scenario</button>
<button id="lab-talk" type="button">Hold to talk</button>
<button id="lab-mockq" type="button">Insert mock question</button>
<p id="lab-voice-status" class="note">Voice: idle.</p>
<div id="lab-result" class="note">Not run yet.</div>

<h2>2. Open-weight comparison</h2>
<p class="note">Advisory critiques only; the deterministic ranking stays
authoritative. Live comparison needs configured runners, otherwise entries
show setup-required (no single partner is confirmed for both models &mdash;
see README). Mock preview uses fixed canned critiques, no network.</p>
<button id="lab-live-btn" type="button">Run live comparison</button>
<button id="lab-mock-btn" type="button">Preview with mock data</button>
<div id="lab-challenge" class="note">Not run yet.</div>

<h2>3. Briefing illustration</h2>
<p class="label">AI-generated illustration (Muse Image) &mdash; illustrative
only. Not a real port image, map, or evidence. Vision evidence comes from
SAM 3.1 segmentation.</p>
<button id="lab-illus-btn" type="button">Generate illustration</button>
<div id="lab-illustration" class="note">Not generated yet.</div>

<footer>
<p>Sources: deterministic scoring (always) &middot; Muse Wonder assumptions
(<code>muse-wonder</code> live, <code>deterministic</code> offline) &middot;
Muse Voice transcription (<code>muse-voice-transcribe</code> live,
<code>setup-required</code> without a key) &middot; open weights
(<code>openweights-local</code>, <code>setup-required</code>, or
<code>mock</code>) &middot; Muse Image illustration
(<code>muse-image</code> live, <code>unavailable</code> offline).</p>
</footer>

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
document.getElementById("lab-run").addEventListener("click", async () => {
  const el = document.getElementById("lab-result");
  el.textContent = "Asking Muse Wonder\\u2026";
  try {
    const q = document.getElementById("lab-input").value;
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
document.getElementById("lab-mockq").addEventListener("click", () => {
  document.getElementById("lab-input").value =
    "What if Rotterdam closes for six more hours?";
  document.getElementById("lab-voice-status").textContent =
    "Voice: mock question inserted (no recording, no network).";
});
let labRecorder = null, labChunks = [], labStopTimer = null;
const labTalk = document.getElementById("lab-talk");
const labVoiceStatus = document.getElementById("lab-voice-status");
function encodeWav(samples, sampleRate) {
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
async function blobToWav16k(blob) {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  try {
    const audio = await ctx.decodeAudioData(await blob.arrayBuffer());
    const src = audio.getChannelData(0);
    const ratio = audio.sampleRate / 16000;
    const len = Math.floor(src.length / ratio);
    const out = new Float32Array(len);
    for (let i = 0; i < len; i++) out[i] = src[Math.floor(i * ratio)];
    return encodeWav(out, 16000);
  } finally {
    await ctx.close();
  }
}
function blobToB64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(String(reader.result).split(",", 2)[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
labTalk.addEventListener("pointerdown", async (e) => {
  e.preventDefault();
  if (labRecorder) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
    labChunks = [];
    labRecorder = new MediaRecorder(stream);
    labRecorder.ondataavailable = (ev) => {
      if (ev.data.size) labChunks.push(ev.data);
    };
    labRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      try {
        labVoiceStatus.textContent = "Voice: transcribing\\u2026";
        const blob = new Blob(labChunks, {type: labRecorder.mimeType});
        const wav = await blobToWav16k(blob);
        const b64 = await blobToB64(wav);
        const result = await postJSON("/demo/north-sea-storm/transcribe",
          {audio_b64: b64, filename: "clip.wav"});
        if (result.text) {
          document.getElementById("lab-input").value = result.text;
          labVoiceStatus.textContent = "[" + result.source + "] transcribed.";
        } else {
          labVoiceStatus.textContent =
            "[" + result.source + "] " + (result.detail || "no transcript");
        }
      } catch (err) { labVoiceStatus.textContent = "Voice: " + String(err); }
      labRecorder = null;
    };
    labRecorder.start();
    labVoiceStatus.textContent = "Recording\\u2026 release to transcribe (max 30s).";
    labStopTimer = setTimeout(() => { if (labRecorder) labRecorder.stop(); }, 30000);
  } catch (err) { labVoiceStatus.textContent = "Microphone unavailable: " + String(err); }
});
function labEndTalk() {
  if (!labRecorder) return;
  clearTimeout(labStopTimer);
  labRecorder.stop();
}
labTalk.addEventListener("pointerup", labEndTalk);
labTalk.addEventListener("pointerleave", labEndTalk);
labTalk.addEventListener("pointercancel", labEndTalk);
async function runChallenge(mock) {
  const el = document.getElementById("lab-challenge");
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
document.getElementById("lab-live-btn").addEventListener("click", () => runChallenge(false));
document.getElementById("lab-mock-btn").addEventListener("click", () => runChallenge(true));
document.getElementById("lab-illus-btn").addEventListener("click", async () => {
  const el = document.getElementById("lab-illustration");
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
</body>
</html>
"""


def render_storm_lab() -> str:
    """Return the Storm Scenario Lab as a self-contained HTML document."""
    return _PAGE
