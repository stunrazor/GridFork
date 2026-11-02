"""Shared Ask GridFork box: one text question, one model answer.

Rendered on the grid, routes, lab, and brief-card pages with a per-page id
prefix. Answers come from ``GET /demo/north-sea-storm/ask`` (Muse Spark
grounded in the deterministic ranking); each question is a paid call and
runs on click only. Output renders via ``textContent`` so model text can
never inject markup.
"""

ASK_PATH = "/demo/north-sea-storm/ask"


def render_ask_box(prefix: str, heading: str = "Ask GridFork") -> str:
    """Render the ask section with ids namespaced under ``prefix``.

    Markup only; :func:`render_ask_script` renders the companion script,
    which pages append after their main script block.
    """
    return f"""<h2>{heading}</h2>
<p class="note">Ask about this incident, the ranking, delays, costs, or data
sources. Each question is a paid Muse Spark call; runs on click only.</p>
<input id="{prefix}-ask-input" maxlength="500" value="Which option is cheapest and what does it trade off?">
<button id="{prefix}-ask-btn" type="button">Ask</button>
<div id="{prefix}-ask-out" class="note">Not asked yet.</div>
"""


def render_ask_script(prefix: str) -> str:
    """Render the ask wiring script for ids namespaced under ``prefix``."""
    return f"""<script>
document.getElementById("{prefix}-ask-btn").addEventListener("click", async () => {{
  const el = document.getElementById("{prefix}-ask-out");
  const q = document.getElementById("{prefix}-ask-input").value.trim();
  if (!q) {{ el.textContent = "Type a question first."; return; }}
  el.textContent = "Asking…";
  try {{
    const res = await fetch("{ASK_PATH}?q=" + encodeURIComponent(q));
    if (!res.ok) {{ el.textContent = "Request failed: HTTP " + res.status + "."; return; }}
    const body = await res.json();
    const ans = body.answer;
    el.textContent = ans.text ? "[" + ans.source + "] " + ans.text
      : "[" + ans.source + "] " + ans.detail;
  }} catch (e) {{ el.textContent = "Request failed."; }}
}});
</script>
"""