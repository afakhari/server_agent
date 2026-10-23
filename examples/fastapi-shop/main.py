from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def home():
    return {"service": "sentinel-demo-shop", "status": "ok"}

@app.get("/health")
def health():
    return {"ok": True}
