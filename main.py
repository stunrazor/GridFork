from fastapi import FastAPI

app = FastAPI(title="GridFork")


@app.get("/health")
def health():
    return {"status": "ok"}
