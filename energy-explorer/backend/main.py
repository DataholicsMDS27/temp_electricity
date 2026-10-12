import importlib
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from .predictor import MockPredictor
from .schemas import Prediction, PredictionResponse, Scenario

MANIFEST = Path(__file__).resolve().parents[1] / "public/data/fsa-index.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    index = json.loads(MANIFEST.read_text())
    app.state.fsas = [entry["fsa"] for entry in index["fsas"]]
    provider = os.getenv("ENERGY_PREDICTOR")
    if provider:
        module, factory = provider.split(":", 1)
        app.state.predictor = getattr(importlib.import_module(module), factory)()
        if app.state.predictor.is_mock:
            raise RuntimeError("A configured real model provider must declare is_mock=False")
    else:
        app.state.predictor = MockPredictor()
    yield


app = FastAPI(title="Ontario Energy Explorer", version="1.0.0", lifespan=lifespan)


@app.get("/api/health")
def health(request: Request):
    return {"status": "ok", "model_version": request.app.state.predictor.model_version}


@app.get("/api/v1/metadata")
def metadata(request: Request):
    predictor = request.app.state.predictor
    return {
        "model_version": predictor.model_version,
        "is_mock": predictor.is_mock,
        "supported_fsas": request.app.state.fsas,
        "temperature": {"min": -30, "max": 30, "step": 1},
        "day_types": ["weekday", "weekend"],
        "interval_minutes": 60,
        "metric": "average_energy_per_customer",
        "unit": "kWh",
        "boundary_version": "statcan-2021",
        "time_convention": predictor.time_convention,
        "legend": {
            "min": request.app.state.predictor.pred_min,
            "max": request.app.state.predictor.pred_max,
            "unit": "kWh/customer",
            "note": "Range of precomputed predictions",
            },
    }


@app.post("/api/v1/predictions", response_model=PredictionResponse)
async def predict(scenario: Scenario, request: Request):
    predictor = request.app.state.predictor
    fsas = request.app.state.fsas
    try:
        rows = await run_in_threadpool(predictor.predict_batch, scenario, fsas)
        rows = [Prediction.model_validate(row) for row in rows]
        if len({row.fsa for row in rows}) != len(rows):
            raise ValueError("Duplicate FSA predictions")
        by_fsa = {row.fsa: row for row in rows}
        if set(by_fsa) - set(fsas):
            raise ValueError("Provider returned unknown FSA codes")
        for row in rows:
            if (row.status == "ok") != (row.value is not None):
                raise ValueError("Prediction value and status are inconsistent")
        complete = [by_fsa.get(fsa, Prediction(fsa=fsa, value=None, status="unsupported")) for fsa in fsas]
        return PredictionResponse(
            request_id=str(uuid4()), scenario=scenario,
            model_version=predictor.model_version, is_mock=predictor.is_mock,
            time_convention=predictor.time_convention, predictions=complete,
        )
    except Exception:
        logging.exception("Prediction provider failed")
        raise HTTPException(status_code=503, detail="Prediction service is unavailable. Please try again.") from None
