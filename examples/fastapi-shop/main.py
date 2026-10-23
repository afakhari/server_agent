"""Disposable Liara Sentinel demo app; never use on a production service."""
import os
from fastapi import FastAPI

app = FastAPI(title="Liara Sentinel test application")


def _require_demo_configuration() -> None:
    # Off by default; this branch exists solely for a controlled SRE demo.
    if os.getenv("SENTINEL_REQUIRE_DEMO_FLAG") == "true" and not os.getenv("SENTINEL_DEMO_FLAG"):
        raise RuntimeError(
            "missing environment variable SENTINEL_DEMO_FLAG "
            "(controlled SRE test, no secrets involved)"
        )


@app.get("/health")
def health():
    _require_demo_configuration()
    return {"ok": True, "service": "sentinel-test"}


@app.get("/")
def root():
    _require_demo_configuration()
    return {"message": "Liara Sentinel disposable demo service"}


if __name__ == "__main__":
    # Liara's default Python entry point can be "python3 main.py".
    # Start a real HTTP server even if platform args aren't applied.
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
