from fastapi import FastAPI

app = FastAPI(title="UFC Style Matchup Engine")


@app.get("/health")
def health():
    return {"status": "ok"}
