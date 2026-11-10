import base64
import binascii

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

import os
from typing import Optional
from fastapi import Header

import live_vessel
import live_weather
import openweights_client
import snapshot as snapshot_mod
import voice_client
from briefing_card import render_brief_card
from grid_page import render_grid_page
from landing_page import render_landing
from routes_page import render_routes_page
from storm_lab import render_storm_lab
from orchestrator import (
    VISION_DEFAULT_IMAGE_URL,
    extract_route_places,
    guidance_response,
    run_challenge,
    run_demo,
    run_demo_with_brief,
    run_demo_with_image,
    run_ask,
    run_demo_with_openweights,
    run_demo_with_summary,
    run_demo_with_vision,
    run_live_snapshot,
    run_whatif,
    validate_ask_question,
)
from license_gate import enforce_license, license_status

app = FastAPI(title="GridFork")

# Optional infrastructure key. Leave unset to disable /v1/cascade.
GRIDFORK_API_KEY = os.getenv("GRIDFORK_API_KEY", "")

# BSL production gate: refuses to boot when GRIDFORK_ENV=production without
# a valid paid license key. Evaluation/dev/test run free, key or not.
enforce_license()

@app.get("/", response_class=HTMLResponse)
def landing():
    return render_landing()


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/license/status")
def license_status_endpoint():
    # Public license mode + build canary. Never exposes secrets.
    return license_status()


@app.get("/demo/north-sea-storm")
def north_sea_storm():
    return run_demo()


@app.get("/demo/north-sea-storm/summary")
def north_sea_storm_summary(
    corridor: str = "",
    from_place: str = Query("", alias="from"),
    to: str = "",
):
    try:
        return run_demo_with_summary(
            snapshot=_stage_snapshot(corridor, from_place, to)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"geocoding failed: {exc}")


@app.get("/demo/north-sea-storm/vision")
def north_sea_storm_vision(
    image_url: str = VISION_DEFAULT_IMAGE_URL,
    corridor: str = "",
    from_place: str = Query("", alias="from"),
    to: str = "",
):
    try:
        return run_demo_with_vision(
            image_url, snapshot=_stage_snapshot(corridor, from_place, to)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"geocoding failed: {exc}")


@app.get("/demo/north-sea-storm/weather")
def north_sea_storm_weather():
    return live_weather.fetch_rotterdam_wind()


@app.get("/demo/north-sea-storm/live")
def north_sea_storm_live():
    return run_live_snapshot()


@app.get("/demo/north-sea-storm/brief")
def north_sea_storm_brief():
    return run_demo_with_brief()


@app.get("/demo/north-sea-storm/image")
def north_sea_storm_image(
    corridor: str = "",
    from_place: str = Query("", alias="from"),
    to: str = "",
):
    try:
        return run_demo_with_image(
            snapshot=_stage_snapshot(corridor, from_place, to)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"geocoding failed: {exc}")


@app.get("/demo/north-sea-storm/openweights")
def north_sea_storm_openweights(model: str = "spark-open"):
    return openweights_client.runner_status(model)


@app.get("/demo/north-sea-storm/openweights/ask")
def north_sea_storm_openweights_ask(model: str = "spark-open"):
    return run_demo_with_openweights(model)


@app.get("/demo/north-sea-storm/ask")
def north_sea_storm_ask(
    q: str = "",
    corridor: str = "",
    from_place: str = Query("", alias="from"),
    to: str = "",
):
    try:
        if corridor:
            return run_ask(
                q, snapshot=snapshot_mod.snapshot_for_corridor(corridor)
            )
        if from_place and to:
            return run_ask(
                q, snapshot=snapshot_mod.snapshot_for_places(from_place, to)
            )
        # Location grounding is worldwide only and comes only from the
        # user: an extracted pair grounds live, anything else gets free
        # guidance instead of a guessed location. Never the demo.
        asked = validate_ask_question(q)
        places = extract_route_places(asked)
        if not places:
            return guidance_response(asked)
        try:
            snap = snapshot_mod.snapshot_for_places(*places)
        except ValueError:
            return guidance_response(asked, places=places)
        except httpx.HTTPError:
            return guidance_response(asked, places=places, unreachable=True)
        return run_ask(asked, snapshot=snap)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"geocoding failed: {exc}")


@app.get("/snapshot")
def world_snapshot(
    corridor: str = "",
    from_place: str = Query("", alias="from"),
    to: str = "",
):
    """Live four-mode ranking for a corridor or two place names."""
    try:
        if corridor:
            return snapshot_mod.snapshot_for_corridor(corridor)
        if from_place and to:
            return snapshot_mod.snapshot_for_places(from_place, to)
        raise ValueError("pass ?corridor=<id> or ?from=<place>&to=<place>")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"geocoding failed: {exc}")


@app.get("/vessels")
def vessel_traffic():
    """Live tracked-vessel counts at the three watched chokepoints.

    A 15 s sample: the community feed is sparse, so short windows read
    near-zero even in busy straits. Boxes reading zero where receivers
    are documented absent (Hormuz, Suez) are listed under
    ``coverage_gaps``; the flag clears itself if vessels appear.
    """
    readout = live_vessel.fetch_vessel_traffic(duration=15.0)
    if readout.get("live"):
        readout["coverage_gaps"] = [
            tag
            for tag in ("hormuz", "suez")
            if readout.get(f"vessels_{tag}") == 0
        ]
    return readout


def _stage_snapshot(corridor: str, from_place: str, to: str):
    """Resolve stage corridor params to a worldwide snapshot or None.

    No params means the incident path; a corridor id or a from/to pair
    builds the asked corridor the stage runs against. Raises ValueError
    and httpx.HTTPError like /snapshot for the caller to translate.
    """
    if corridor:
        return snapshot_mod.snapshot_for_corridor(corridor)
    if from_place and to:
        return snapshot_mod.snapshot_for_places(from_place, to)
    return None


@app.get("/demo/north-sea-storm/whatif")
def north_sea_storm_whatif(
    q: str = "",
    corridor: str = "",
    from_place: str = Query("", alias="from"),
    to: str = "",
):
    try:
        return run_whatif(
            q, snapshot=_stage_snapshot(corridor, from_place, to)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"geocoding failed: {exc}")


@app.get("/demo/north-sea-storm/challenge")
def north_sea_storm_challenge(
    models: str = "spark-open,glimmer",
    mock: bool = False,
    corridor: str = "",
    from_place: str = Query("", alias="from"),
    to: str = "",
):
    keys = [m.strip() for m in (models or "").split(",") if m.strip()]
    try:
        return run_challenge(
            keys or ["spark-open", "glimmer"],
            mock=mock,
            snapshot=_stage_snapshot(corridor, from_place, to),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"geocoding failed: {exc}")


@app.post("/demo/north-sea-storm/transcribe")
def north_sea_storm_transcribe(payload: dict):
    """Transcribe a browser-recorded WAV clip sent as base64 JSON.

    JSON keeps the endpoint dependency-free (no multipart parser needed).
    Only 400s for a missing/empty/oversize/undecodable upload; voice API
    failures return ``source: "unavailable"`` with HTTP 200, like the
    other advisory endpoints.
    """
    raw = payload.get("audio_b64") or ""
    if "," in raw:  # tolerate a data:audio/wav;base64, URL prefix
        raw = raw.split(",", 1)[1]
    try:
        audio = base64.b64decode(raw, validate=True) if raw else b""
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="audio_b64 is not valid base64")
    if not audio:
        raise HTTPException(status_code=400, detail="no audio uploaded")
    if len(audio) > voice_client.MAX_BYTES:
        raise HTTPException(status_code=400, detail="audio exceeds the 32 MB cap")
    filename = str(payload.get("filename") or "clip.wav")[:100]
    return voice_client.transcribe_audio(audio, filename)


@app.get("/demo/grid", response_class=HTMLResponse)
def demo_grid():
    return render_grid_page()


@app.get("/demo/north-sea-storm/brief-card", response_class=HTMLResponse)
def north_sea_storm_brief_card():
    return render_brief_card(run_demo())


@app.get("/demo/storm-lab", response_class=HTMLResponse)
def north_sea_storm_lab():
    return render_storm_lab()


@app.get("/demo/routes", response_class=HTMLResponse)
def north_sea_storm_routes():
    return render_routes_page(run_demo())

@app.post("/v1/cascade")
def cascade(
    body: dict,
    authorization: Optional[str] = Header(None),
):
    """Authenticated ranking endpoint. Same engine as the demo.
    Disabled unless GRIDFORK_API_KEY is set."""
    if not GRIDFORK_API_KEY:
        raise HTTPException(status_code=503, detail="API disabled: GRIDFORK_API_KEY not set")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != GRIDFORK_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    from_place = (body.get("from") or "").strip()
    to_place = (body.get("to") or "").strip()
    if not from_place or not to_place:
        raise HTTPException(status_code=400, detail="Both 'from' and 'to' are required")

    try:
        result = run_live_snapshot(from_place=from_place, to_place=to_place)
    except TypeError:
        result = run_live_snapshot()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ranking failed: {exc}")

    return {
        "from": from_place,
        "to": to_place,
        "ranked_options": result.get("ranked_options", []),
        "findings": result.get("findings", []),
        "top_reasons": result.get("top_reasons", []),
        "provenance": result.get("provenance", {}),
    }
