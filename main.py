from fastapi import FastAPI

from orchestrator import run_demo, run_demo_with_summary

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
