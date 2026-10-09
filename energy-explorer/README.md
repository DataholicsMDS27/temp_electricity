# Ontario Energy Explorer

A desktop scenario explorer built with React, TypeScript, Vite, MapLibre GL JS, Radix controls and FastAPI. It maps average electricity consumption per customer (kWh during a selected hour) across **520 Ontario census FSAs**.

## Run locally

Requires Node 22+ and Python 3.11+. From this directory:

```bash
npm ci
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock.txt
```

Start the API and frontend in separate terminals:

```bash
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```bash
npm run dev
```

Open http://127.0.0.1:5173. API documentation is at http://127.0.0.1:8000/docs.

## Features

- Temperature from −40 to 35 °C in 1 °C steps, applied to all FSAs.
- Weekday/weekend selection and a looping hourly interval wheel.
- Solid Light and Dark themes; Daylight's pixel sky follows the chosen hour.
- Daylight uses the light basemap from 06:00 to 18:00, otherwise dark. This is a decorative clock cycle, not an astronomical sunrise calculation.
- FSA search, hover inspection, persistent selection, province/southern Ontario views.
- Fixed consumption scale, explicit missing values, submit/loading/error/retry states, and results labelled with their submitted scenario.
- Local font files and static boundary geometry; external basemap tiles have a bundled Natural Earth fallback.

**Predictions are synthetic demo values until a real provider is connected.** No consumption training dataset has been supplied to this app. The demo formula is deterministic and is not a fitted energy model.

## Plug in the model

The browser calls `POST /api/v1/predictions` with:

```json
{"temperature_c":22,"day_type":"weekday","hour":14}
```

`hour` is the start of the interval (`14` means 14:00–15:00; `23` means 23:00–00:00). Model timezone conventions must be confirmed by the modelling team before real predictions are enabled. The HTTP API returns the submitted scenario, model version, mock flag, units, interval and values keyed by FSA.

Implement the protocol in `backend/predictor.py`. A provider owns model loading, static regional features, preprocessing, feature order and inference. Its factory is called once at startup:

```python
from backend.schemas import Prediction

class ModelPredictor:
    model_version = "your-model-v1"
    is_mock = False
    time_convention = "Describe the training timestamp convention here"

    def __init__(self):
        # Load model, fitted preprocessing and static FSA features once.
        pass

    def predict_batch(self, scenario, fsa_codes):
        # Build features and run your model, returning Prediction objects.
        # Use value=None, status='unsupported' for unsupported FSAs.
        raise NotImplementedError

def create_predictor():
    return ModelPredictor()
```

Set `ENERGY_PREDICTOR=your_package:create_predictor` when starting the API. A configured provider failure stops startup; it never silently falls back to the mock. Missing returned FSAs are completed as unsupported; duplicate/unknown FSA identifiers, negative/non-finite values, and inconsistent statuses are rejected. Inference runs in a thread so it does not block the server event loop; providers should handle concurrent calls safely or serialize internally.

Before integration, reconcile your supported FSA list with `public/data/fsa-index.json`, confirm timezone and valid temperature limits, and calibrate the fixed legend in `/api/v1/metadata` (currently 0–4 kWh/customer for the demo). The temperature request schema and metadata must be updated together if model limits change. Customer averages are not summed into provincial totals.

## Data provenance

- FSA source: [Statistics Canada 2021 Census Forward Sortation Area Boundary File](https://www150.statcan.gc.ca/n1/en/catalogue/92-179-X2021001).
- Geometry downloaded from the [cartographic FSA REST layer](https://geo.statcan.gc.ca/geo_wa/rest/services/2021/Cartographic_boundary_files/MapServer/14), filtered to `PRUID='35'`, converted by the service to EPSG:4326 and generalized at 0.0003 degrees. Normalized using `scripts/prepare_boundaries.py`.
- Census-derived geography, not a current authoritative Canada Post delivery-boundary inventory. Coverage is all Ontario FSAs in this census source, which may differ from a newer consumption dataset.
- Basemap styles adapted from [OpenFreeMap](https://openfreemap.org/); tiles from OpenMapTiles/OpenStreetMap. Attribution remains displayed on the map. Styles are stored locally; tiles, glyphs and sprites are fetched from the provider.
- Offline geographic context: [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/), public-domain 110m land and lake outlines.

## Verify

```bash
npm run build
.venv/bin/python -m unittest backend.test_contract
.venv/bin/python -m unittest backend.test_production # requires dist/ from the build
npm run verify # requires the API on port 8000
```

## Deployment

The production entrypoint serves the built frontend and Python API from the same origin. The Docker image builds the frontend, installs locked Python dependencies, and runs as an unprivileged user. Hosting supplies HTTPS and the public hostname. A database is not required for this MVP.

```bash
docker build -t ontario-energy-explorer .
docker run --rm -p 10000:10000 ontario-energy-explorer
```

Open http://localhost:10000. Without Docker, run `npm run build` then `.venv/bin/python -m uvicorn backend.production:app --host 0.0.0.0 --port 10000`.

### Render

In the team repository, use the **root** `render.yaml`; it sets `rootDir: energy-explorer`. For a manual service, select the app branch and set Root Directory to `energy-explorer`, Dockerfile to `./Dockerfile`, and health check to `/api/health`.

For the full trained-model handoff and runnable integration checker, see [MODEL_INTEGRATION.md](docs/MODEL_INTEGRATION.md).

Push this directory as a Git repository, connect it in the Render dashboard, and create a Blueprint using the included `render.yaml`. It defines one Docker web service with `/api/health` checks. Alternatively create a Docker web service manually from this repository, using the root Dockerfile and the same health-check path. Share the HTTPS URL Render assigns after the deployment is live.

The Blueprint selects the free plan to avoid initiating paid hosting. Free Render web services sleep after 15 minutes without requests, so the first visit after inactivity can be slower. Choose a paid instance in the dashboard if you need an always-on presentation. See [Render's free service limits](https://render.com/docs/free).

For the trained model, include its package and artifacts in the image, add required Python dependencies to the lock file, and configure `ENERGY_PREDICTOR=your_package:create_predictor` in the host's environment settings. Redeploy and verify `/api/v1/metadata` reports `is_mock=false`. Keep credentials in host-managed environment variables.

The image also works on other container hosts. Bind to the supplied `PORT`, configure `/api/health`, and keep at least one worker process running. Each worker loads its own model, so choose the worker count according to model memory usage.

The UI is designed and verified primarily for desktop. Narrow-screen layout is a basic fallback, not a mobile product specification.
