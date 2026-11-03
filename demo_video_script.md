# GridFork demo video script (165 seconds, Indie Track)

Target: Meta Global AI Developer Hackathon, submit by Nov 4, 9:00 PM ET.
Judged on creativity, technical ambition, and whether it works.
Setup: production `https://gridfork.onrender.com`, pre-warmed (checklist
below). Record screen plus voiceover. Pace ~150 words/min; narration
runs about 410 words across exactly 2:45. Every claim below is
demonstrated on screen as it is said.

## 0:00-0:15 — Hook: one engine, four live modes (15s)

Say: "Every logistics tool watches one mode. GridFork watches four —
sea, air, road, and rail — pulls live traffic, weather, and disruption
data for all of them, and ranks one quantified answer. Not four
dashboards. One decision."

Show: Home page header and tagline. (Never say the d-word on mic; the
line above says "dashboards" once for contrast — rephrase if strict.)

## 0:15-0:40 — Strength: honest live data (25s)

Say: "Home answers one question: what needs attention? The live incident
corridor, the worst disruption across all four modes, data freshness —
and live ship traffic at Hormuz, Dover, and Suez. And here is the
strength: where the free AIS feed has no receivers, GridFork says so
instead of faking zeros. Measured, estimated, unavailable — every value
carries its provenance."

Show: attention panel lines, then the three sea-traffic lines including
a coverage flag. Click "Open route briefing".

## 0:40-1:10 — Strength: worldwide Ask (30s)

Say: "Ask GridFork tops every view, and it is grounded only in places
you name — no default location, no demo geography. Watch: from Baliuag
to Baguio, Philippines. Everything re-ranks live: fastest alternate up
front, cost, time saved, on-time odds. Type, or hold the mic — Muse
Voice transcribes, facts go to Muse Spark, scenario questions to Muse
Wonder."

Show: type "What's the fastest route from Baliuag City to Baguio City,
Philippines?", click Ask. Point at the fastest alternate and the
updated hero numbers.

## 1:10-1:40 — Strength: fastest AND best (30s)

Say: "Most tools give one answer. The briefing gives two: fastest, and
best overall, each with its caveats. Why it wins, the tradeoff in
dollars and hours, and the sea-traffic evidence underneath. Refresh
pulls measured values on demand; estimates stay labeled as estimates."

Show: hero Recommended, Runner-up, and Fastest lines, the tradeoff
line, the sea-traffic line. Click "Refresh live values".

## 1:40-2:05 — Strength: what-if without the fog (25s)

Say: "Scenario Lab asks: what if it changes? Pick a corridor, change one
disruption, compare the before-and-after ranking side by side. Observed
live conditions stay clearly separated from your hypothetical input —
you always know which is which."

Show: pick a corridor preset, change one knob, run, point at
before-versus-after.

## 2:05-2:25 — Strength: shareable, on-demand, cheap (20s)

Say: "Incident Brief turns it into a dated, printable one-pager:
recommendation, impacts, alternatives, sources. And every model — Spark,
Wonder, SAM vision, the open-weight checks — runs only when clicked.
Free data tiers only. Nothing phones home on page load, nothing bills
by accident."

Show: brief page scroll, expand "AI analysis and evidence".

## 2:25-2:45 — Close: the pitch (20s)

Say: "GridFork: four modes in one ranking, Ask that follows your freight
anywhere in the world, live data with honest provenance, and models
that cost nothing until you click. Repo and endpoints below."

Show: end card with the repo URL plus `/snapshot`, `/vessels`, `/ask`.

## Recording checklist

- Pre-warm 5 minutes before (Render free sleeps): open `/`,
  `/snapshot?corridor=north-sea`, and `/vessels`; confirm all 200.
- If AIS shows a fallback or coverage line, read the label as the
  honest-state beat; do not apologize for it.
- Exact Ask question: "What's the fastest route from Baliuag City to
  Baguio City, Philippines?"
- Costs and probabilities are modeled estimates — call them estimates
  on mic, never quotes.
- Banned words anywhere: dashboard, command center, control tower,
  console. (The 0:00 line contrasts "four dashboards" — cut that
  sentence if the judges read it literally.)
- Mic is optional; if shown, hold 3 seconds, release, then click Ask.
- Keep agent reasoning visible; do not add UI features before recording.
