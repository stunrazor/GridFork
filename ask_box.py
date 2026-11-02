"""Shared Ask GridFork box: one text question, one model answer.

Rendered on the grid, routes, lab, and brief-card pages with a per-page id
prefix. Answers come from ``GET /demo/north-sea-storm/ask`` (Muse Spark
grounded in the deterministic ranking); each question is a paid call and
runs on click only. A hold-to-talk button dictates the question via Muse
Voice Transcribe (paid per audio hour); sending still needs the click.
Output renders via ``textContent`` so model text can never inject markup.
"""

ASK_PATH = "/demo/north-sea-storm/ask"
TRANSCRIBE_PATH = "/demo/north-sea-storm/transcribe"


def render_ask_box(prefix: str, heading: str = "Ask GridFork") -> str:
    """Render the ask section with ids namespaced under ``prefix``.

    Markup only; :func:`render_ask_script` renders the companion script,
    which pages append after their main script block.
    """
    return f"""<h2>{heading}</h2>
<p class="note">Ask for the fastest route between any two places, anywhere
in the world &mdash; live traffic, disruptions, costs, and ranking.
Scenario and why-questions go to Muse Wonder, facts to Muse Spark; each
answered question is a paid call and runs on click only.</p>
<input id="{prefix}-ask-input" maxlength="500" value="Which option is cheapest and what does it trade off?">
<button id="{prefix}-ask-btn" type="button">Ask</button>
<button id="{prefix}-ask-talk" type="button">Hold to talk</button>
<span id="{prefix}-ask-voice" class="note"></span>
<div id="{prefix}-ask-out" class="ask-out">Not asked yet.</div>
"""


def render_ask_script(prefix: str, extra: str = "") -> str:
    """Render the ask wiring script for ids namespaced under ``prefix``.

    ``extra`` is a JS expression appended to the request URL, so a page
    can ground Ask in its own context (the lab appends its corridor).
    """
    return f"""<script>
document.getElementById("{prefix}-ask-btn").addEventListener("click", async () => {{
  const el = document.getElementById("{prefix}-ask-out");
  const q = document.getElementById("{prefix}-ask-input").value.trim();
  if (!q) {{ el.textContent = "Type a question first."; return; }}
  el.textContent = "Asking…";
  try {{
    const res = await fetch("{ASK_PATH}?q=" + encodeURIComponent(q){extra});
    if (!res.ok) {{ el.textContent = "Request failed: HTTP " + res.status + "."; return; }}
    const body = await res.json();
    const ans = body.answer;
    const fa = body.fastest_alternative;
    const ctx = body.grounded_on ? "About " + body.grounded_on + ". " : "";
    const first = fa ? "Fastest alternate: " + fa.option_id +
      " (" + fa.total_hours + "h total). " : "";
    el.textContent = ans.text ? ctx + first + "[" + ans.source + "] " + ans.text
      : ctx + first + "[" + ans.source + "] " + ans.detail;
    if (body.snapshot && typeof window["{prefix}AskSnapshot"] === "function") {{
      window["{prefix}AskSnapshot"](body.snapshot);
    }}
  }} catch (e) {{ el.textContent = "Request failed."; }}
}});
const {prefix}AskTalk = document.getElementById("{prefix}-ask-talk");
const {prefix}AskVoice = document.getElementById("{prefix}-ask-voice");
let {prefix}AskRecorder = null, {prefix}AskChunks = [], {prefix}AskStopTimer = null;
function {prefix}AskEncodeWav(samples, sampleRate) {{
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  function writeStr(offset, s) {{
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
  }}
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
  for (let i = 0; i < samples.length; i++) {{
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }}
  return new Blob([buffer], {{type: "audio/wav"}});
}}
async function {prefix}AskBlobToWav16k(blob) {{
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  try {{
    const audio = await ctx.decodeAudioData(await blob.arrayBuffer());
    const src = audio.getChannelData(0);
    const ratio = audio.sampleRate / 16000;
    const len = Math.floor(src.length / ratio);
    const out = new Float32Array(len);
    for (let i = 0; i < len; i++) out[i] = src[Math.floor(i * ratio)];
    return {prefix}AskEncodeWav(out, 16000);
  }} finally {{
    await ctx.close();
  }}
}}
function {prefix}AskBlobToB64(blob) {{
  return new Promise((resolve, reject) => {{
    const reader = new FileReader();
    reader.onloadend = () => resolve(String(reader.result).split(",", 2)[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  }});
}}
{prefix}AskTalk.addEventListener("pointerdown", async (e) => {{
  e.preventDefault();
  if ({prefix}AskRecorder) return;
  try {{
    const stream = await navigator.mediaDevices.getUserMedia({{audio: true}});
    {prefix}AskChunks = [];
    {prefix}AskRecorder = new MediaRecorder(stream);
    {prefix}AskRecorder.ondataavailable = (ev) => {{
      if (ev.data.size) {prefix}AskChunks.push(ev.data);
    }};
    {prefix}AskRecorder.onstop = async () => {{
      stream.getTracks().forEach(t => t.stop());
      try {{
        {prefix}AskVoice.textContent = "Transcribing…";
        const blob = new Blob({prefix}AskChunks, {{type: {prefix}AskRecorder.mimeType}});
        const wav = await {prefix}AskBlobToWav16k(blob);
        const b64 = await {prefix}AskBlobToB64(wav);
        const res = await fetch("{TRANSCRIBE_PATH}", {{method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{audio_b64: b64, filename: "ask.wav"}})}});
        const result = await res.json();
        if (result.text) {{
          document.getElementById("{prefix}-ask-input").value = result.text;
          {prefix}AskVoice.textContent = "[" + result.source + "] transcribed. Click Ask to send.";
        }} else {{
          {prefix}AskVoice.textContent = "[" + result.source + "] " + (result.detail || "no transcript");
        }}
      }} catch (err) {{ {prefix}AskVoice.textContent = "Transcription failed."; }}
      {prefix}AskRecorder = null;
    }};
    {prefix}AskRecorder.start();
    {prefix}AskVoice.textContent = "Recording… release to transcribe (max 30s).";
    {prefix}AskStopTimer = setTimeout(() => {{ if ({prefix}AskRecorder) {prefix}AskRecorder.stop(); }}, 30000);
  }} catch (err) {{ {prefix}AskVoice.textContent = "Microphone unavailable."; }}
}});
function {prefix}AskEndTalk() {{
  if (!{prefix}AskRecorder) return;
  clearTimeout({prefix}AskStopTimer);
  {prefix}AskRecorder.stop();
}}
{prefix}AskTalk.addEventListener("pointerup", {prefix}AskEndTalk);
{prefix}AskTalk.addEventListener("pointerleave", {prefix}AskEndTalk);
{prefix}AskTalk.addEventListener("pointercancel", {prefix}AskEndTalk);
</script>
"""