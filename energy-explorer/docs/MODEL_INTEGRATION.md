# Plug in and test a trained model

All commands below run from `energy-explorer/`, not the repository root. The research project uses a separate Python environment; the deployed API currently uses Python 3.12. Export and test artifacts with compatible Python and library versions before deployment.

## 1. Agree on the prediction contract

The API accepts `{"temperature_c":22,"day_type":"weekday","hour":14}`. Temperature is an integer from −40 to 35 °C applied to every FSA. Day type is `weekday` or `weekend`. Hour is 0–23 in 24-hour time and denotes the start of a one-hour interval; 23 means 23:00–00:00.

Return **average kWh per customer during that hour**, not total FSA consumption or instantaneous kW. Derive the training target using the appropriate customer denominator for each observation; distinguish residential customers from small business customers if the source combines them. Document aggregation, missing values, and denominator changes. The interface describes a typical day type, not a forecast for a specific date. If training uses month, season, holidays, or other features, define a defensible aggregation or fixed scenario internally; do not quietly invent a calendar date.

Confirm timestamp timezone and daylight saving conventions against the training data. Set `time_convention` to that exact convention. Reconcile supported codes with `public/data/fsa-index.json`: these are 520 Ontario **2021 census** FSAs, which may differ from the consumption dataset's codes. Preserve three-character uppercase FSA identifiers. Omit unsupported codes or return an explicit null status; never invent zero consumption.

## 2. Package the model and preprocessing

Export the fitted preprocessing and regressor together where possible (for example, a scikit-learn Pipeline). Save feature names/order, fitted category encodings, target transformation, library versions, and any fixed FSA features with the artifact. Keep model files under `backend/models/` or another explicit path. The current Dockerfile copies `backend/`, so files there are included in the image; a model stored elsewhere requires a Dockerfile COPY instruction. Do not commit training data or credentials. For a large or private artifact, arrange a secure build/download step or host secret file and verify that the runtime user can read it.

Install inference dependencies in the explorer's `.venv` and record tested, pinned versions in `backend/requirements.lock.txt`. Update `backend/requirements.txt` as appropriate. The research root `pyproject.toml` is not installed by the app's Docker image. Only load artifacts from trusted sources: pickle/joblib deserialization executes Python code.

## 3. Implement the provider

Create `backend/model_provider.py`. The module must expose a no-argument factory returning an object with `model_version`, `is_mock=False`, `time_convention`, and `predict_batch(scenario, fsa_codes)`. The API loads it once at startup and runs batch inference in a thread. Make shared inference thread-safe or protect it with a lock.

This example assumes a fitted pipeline accepting a pandas DataFrame with the four named columns. Adapt the features, categories, artifact format, and output transformation to the training pipeline; these column names are an example, not a claim about the team's model.

```python
from pathlib import Path
from threading import Lock
import joblib
import pandas as pd
from .schemas import Prediction

class ModelPredictor:
    model_version = "electricity-v1"
    is_mock = False
    # Replace with the verified training timestamp convention.
    time_convention = "REPLACE WITH VERIFIED TRAINING TIME CONVENTION"

    def __init__(self):
        root = Path(__file__).resolve().parent / "models"
        self.pipeline = joblib.load(root / "pipeline.joblib")
        self.supported = set(pd.read_csv(root / "supported_fsas.csv")["fsa"])
        self.lock = Lock()

    def predict_batch(self, scenario, fsa_codes):
        supported = [fsa for fsa in fsa_codes if fsa in self.supported]
        if not supported:
            return []
        features = pd.DataFrame({
            "fsa": supported,
            "temperature_c": scenario.temperature_c,
            "day_type": scenario.day_type,
            "hour": scenario.hour,
        })
        with self.lock:
            values = self.pipeline.predict(features)
        if len(values) != len(supported):
            raise ValueError("Model output length does not match the input batch")
        return [Prediction(fsa=fsa, value=float(value), status="ok")
                for fsa, value in zip(supported, values)]

def create_predictor():
    return ModelPredictor()
```

If the model predicts a log target or total consumption, apply the scientifically appropriate inverse transformation or normalization before returning values. Do not arbitrarily clamp negative predictions to hide a model error. Unknown/duplicate FSA codes, negative/non-finite values, or inconsistent value/status pairs cause a 503 response. Omitted known FSAs become `unsupported` with `value=null`. Use `unavailable` with null for temporarily unavailable predictions. A configured provider that fails to load stops startup; the API does not silently switch to demo mode.

## 4. Run locally and test

```bash
npm ci
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock.txt
npm run build
.venv/bin/python -m unittest backend.test_contract backend.test_production
```

Those five tests verify the API contract using demo predictions and production routing; they do **not** verify a trained model. After implementing and packaging the provider, run:

```bash
ENERGY_PREDICTOR=backend.model_provider:create_predictor \
  .venv/bin/python -m backend.check_model
```

This separate checker requires a real provider, checks startup and metadata, exercises 40 scenarios across temperature endpoints, both day types and key hourly intervals, verifies FSA coverage/statuses/units, and rejects out-of-range input. It permits unsupported FSAs but requires at least one usable prediction in each scenario. Add provider-specific tests for known expected values, preprocessing categories, missing static features, artifact compatibility, determinism when expected, and concurrent inference. Test with a representative load and measure latency/memory before choosing hosting compute.

Then start the actual production server:

```bash
ENERGY_PREDICTOR=backend.model_provider:create_predictor \
  .venv/bin/python -m uvicorn backend.production:app --host 127.0.0.1 --port 10000
```

Open http://127.0.0.1:10000. Confirm `/api/v1/metadata` reports `is_mock=false` and the expected version/time convention. Submit inputs in the UI, search a supported FSA, and inspect its predicted value. Unsupported FSAs should use the missing-value treatment. Verify min/max temperatures, weekend, and 23:00–00:00.

```bash
curl --fail http://127.0.0.1:10000/api/health
curl --fail http://127.0.0.1:10000/api/v1/metadata
curl --fail -X POST http://127.0.0.1:10000/api/v1/predictions \
  -H 'Content-Type: application/json' \
  -d '{"temperature_c":22,"day_type":"weekday","hour":14}'
```

## 5. Evaluate accuracy separately

Use a held-out time period and avoid leakage between training and test observations. Compare against simple baselines and report MAE/RMSE in kWh/customer, with breakdowns by FSA, temperature range, hour, and day type. Check training coverage at −40 and 35 °C; document extrapolation or change API limits and slider metadata together if unsupported. Integration passing says nothing about accuracy or uncertainty. Calibrate the fixed legend in `backend/main.py` using the real output range; remove its demo-only note. Keep regional averages separate from provincial totals.

## 6. Deploy the model

The root `render.yaml` uses `rootDir: energy-explorer`, Docker, port 10000, and `/api/health`. A manually configured Render service needs the same root directory and Dockerfile path `./Dockerfile`.

1. Commit provider code, dependency updates, and the artifact packaging configuration to the deployed branch.
2. Set `ENERGY_PREDICTOR=backend.model_provider:create_predictor` in Render's Environment settings. Keep any artifact credentials in secret environment variables, not Git.
3. Deploy the selected branch and inspect startup logs/health checks. Each worker loads its own model; free hosting has only 512 MB RAM and sleeps after inactivity. Upgrade only if memory or availability requirements justify it.
4. Check the public `/api/v1/metadata` and `/api/v1/predictions`, then the map. Verify `is_mock=false`, version, units, and a known FSA value against a local run of the same artifact.
5. Roll back to the last working code/artifact pair if checks fail. Do not remove `ENERGY_PREDICTOR` as a silent fallback to synthetic predictions.

For training or dependencies that require Python 3.14, change the Docker runtime deliberately and regenerate/test the inference lock file in that version; do not assume the research and deployment environments are compatible.
