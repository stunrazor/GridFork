# GridFork demo video script (3 minutes, Indie Track)

Target: Meta Global AI Developer Hackathon, submit by Nov 4, 9:00 PM ET.
Judged on creativity, technical ambition, and whether it works.
Setup: `uvicorn main:app --port 8000` with `META_MODEL_API_KEY` set, browser
at `http://127.0.0.1:8000/demo/grid`. Record screen plus voiceover.

## 0:00-0:20 — Problem

Say: "When a North Sea storm shuts Rotterdam, the cascade hits every mode —
port queues, truck backups, air overload, missed rail links. Single-mode
tools never see the whole picture. GridFork ranks one quantified response."

Show: concept one-liner on the grid page header.

## 0:20-1:00 — Live grid, storm injected

Say: "Four specialists report: sea disrupted, air degraded, road and rail
absorbing. The orchestrator scores every reroute on cost, time saved,
on-time probability, and confidence."

Show: scroll findings row, then the ranked table. Point at rank 1.

## 1:00-1:40 — SAM visual verification

Say: "Then visual ground truth. SAM 3.1 segments the container stacks —
seven detections, congestion 0.7 — and the sea leg takes eight more hours
of port delay. The ranking absorbs real pixels, not just estimates."

Show: click "Run SAM verification", read the result line aloud.

## 1:40-2:30 — Ranking climax

Say: "Rail-reroute stays on top at 0.80; the Spark rationale calls the
tradeoff against road in dollars and hours. Live Rotterdam wind rides
alongside as the one real-world layer."

Show: top table row, narrative summary line, weather line.

## 2:30-3:00 — Result and technical note

Say: "End to end: synthetic storm in, ranked quantified reroutes out, with
Spark reasoning and SAM vision attached — and every endpoint still works
offline on deterministic fallbacks."

Show: full page scroll. End card: repo plus endpoint list.

## Recording checklist

- Key set in the terminal that runs uvicorn (shows `muse-spark`/`sam-3.1`).
- No "command center", "control tower", or "dashboard" wording anywhere.
- Keep agent reasoning visible; do not add UI features mid-week.
