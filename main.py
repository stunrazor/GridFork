import base64
import binascii

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

import live_weather
import openweights_client
import voice_client
from briefing_card import render_brief_card
from grid_page import render_grid_page
from landing_page import render_landing
from routes_page import render_routes_page
from storm_lab import render_storm_lab
from orchestrator import (
    VISION_DEFAULT_IMAGE_URL,
    run_challenge,
    run_demo,
    run_demo_with_brief,
    run_demo_with_image,
    run_demo_with_openweights,
    run_demo_with_summary,
    run_demo_with_vision,
    run_live_snapshot,
    run_whatif,
)

app = FastAPI(title="GridFork")


@app.get("/", response_class=HTMLResponse)
def landing():
    return render_landing()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/demo/north-sea-storm")
def north_sea_storm():
    return run_demo()


@app.get("/demo/north-sea-storm/summary")
def north_sea_storm_summary():
    return run_demo_with_summary()


@app.get("/demo/north-sea-storm/vision")
def north_sea_storm_vision(image_url: str = VISION_DEFAULT_IMAGE_URL):
    return run_demo_with_vision(image_url)


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
def north_sea_storm_image():
    return run_demo_with_image()


@app.get("/demo/north-sea-storm/openweights")
def north_sea_storm_openweights(model: str = "spark-open"):
    return openweights_client.runner_status(model)


@app.get("/demo/north-sea-storm/openweights/ask")
def north_sea_storm_openweights_ask(model: str = "spark-open"):
    return run_demo_with_openweights(model)


@app.get("/demo/north-sea-storm/whatif")
def north_sea_storm_whatif(q: str = ""):
    try:
        return run_whatif(q)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/demo/north-sea-storm/challenge")
def north_sea_storm_challenge(models: str = "spark-open,glimmer", mock: bool = False):
    keys = [m.strip() for m in (models or "").split(",") if m.strip()]
    try:
        return run_challenge(keys or ["spark-open", "glimmer"], mock=mock)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


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
