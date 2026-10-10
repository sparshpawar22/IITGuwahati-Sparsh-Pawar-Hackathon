from fastapi import FastAPI

app = FastAPI(title="NLP Risk Engine")

@app.get("/health")
def health():
    return {"status": "ok", "service": "nlp-risk-engine"}