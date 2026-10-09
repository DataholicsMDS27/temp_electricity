"""Production entrypoint: serve the built UI and prediction API together."""

import os
from pathlib import Path

from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from .main import app

static_directory = Path(os.getenv("ENERGY_STATIC_DIR", Path(__file__).resolve().parents[1] / "dist"))
if not (static_directory / "index.html").is_file():
    raise RuntimeError("The frontend build is missing. Run npm run build before starting production.")

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Register after API routes so /api always reaches the Python service.
app.mount("/", StaticFiles(directory=static_directory, html=True), name="frontend")
