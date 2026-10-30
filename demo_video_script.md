# GridFork demo video script (3 minutes, Indie Track)

Target: Meta Global AI Developer Hackathon, submit by Nov 4, 9:00 PM ET.
Judged on creativity, technical ambition, and whether it works.
Setup: `uvicorn main:app --port 8000` with `META_MODEL_API_KEY` set, browser
at `http://127.0.0.1:8000/demo/grid`. Record screen plus voiceover.

## 0:00-0:15 — Problem

Say: "When a North Sea storm shuts Rotterdam, the cascade hits every mode.
Single-mode tools never see the whole picture. GridFork ranks one
quantified response."

Show: concept one-liner on the grid page header.

## 0:15-0:50 — Live grid, storm injected

Say: "Four specialists report: sea disrupted, the rest absorbing. The
orchestrator scores every reroute on cost, time saved, on-time
probability, and confidence. Rail-reroute leads."

Show: findings row, then the ranked table. Point at rank 1.

## 0:50-1:20 — SAM visual verification

Say: "Then visual ground truth. SAM 3.1 segments the container stacks —
seven detections, congestion 0.7 — and the sea leg takes eight more hours
of port delay. Real pixels, not just estimates."

Show: click "Run SAM verification", read the result line aloud.

## 1:20-1:55 — Ranking climax

Say: "Rail stays on top at 0.80; the Spark rationale calls the tradeoff
against road in dollars and hours. Live Rotterdam wind rides alongside."

Show: top table row, narrative summary line, weather line.

## 1:55-2:25 — Meta Models, on demand

Say: "The optional Meta Models section adds Wonder, Image, and the
open weights — nothing runs until clicked. Wonder explains the decision
in four labeled lines. Image generates the storm illustration, clearly
separate from SAM's measured segmentation. The open-weight checks
report honest setup state until a local runner exists."

Show: click "Explain this scenario", read the brief labels. Click
"Generate port image", show the illustration. Click one runner check,
read the setup-required line.

## 2:25-3:00 — Result and technical note

Say: "End to end: synthetic storm in, ranked quantified reroutes out,
with four live Meta models attached — Spark, SAM, Wonder, Image — plus
wired open-weight integrations and deterministic fallbacks throughout."

Show: full page scroll. End card: repo plus endpoint list.

## Recording checklist

- Key set in the terminal that runs uvicorn (shows `muse-spark`,
  `sam-3.1`, `muse-wonder`, `muse-image`).
- Open-weight checks will show `setup-required`: read the line as the
  honest-state beat, do not apologize for it.
- No "command center", "control tower", or "dashboard" wording anywhere.
- Keep agent reasoning visible; do not add UI features mid-week.
