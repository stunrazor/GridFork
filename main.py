from fastapi import FastAPI
from fastapi.responses import HTMLResponse

import live_weather
import openweights_client
from grid_page import render_grid_page
from orchestrator import (
    VISION_DEFAULT_IMAGE_URL,
    run_demo,
    run_demo_with_brief,
    run_demo_with_image,
    run_demo_with_summary,
    run_demo_with_vision,
)

app = FastAPI(title="GridFork")


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


@app.get("/demo/north-sea-storm/brief")
def north_sea_storm_brief():
    return run_demo_with_brief()


@app.get("/demo/north-sea-storm/image")
def north_sea_storm_image():
    return run_demo_with_image()


@app.get("/demo/north-sea-storm/openweights")
def north_sea_storm_openweights(model: str = "spark-open"):
    return openweights_client.runner_status(model)


@app.get("/demo/grid", response_class=HTMLResponse)
def demo_grid():
    return render_grid_page()
