from fastapi import FastAPI

from orchestrator import run_demo

app = FastAPI(title="GridFork")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/demo/north-sea-storm")
def north_sea_storm():
    return run_demo()
