# Energy Explorer

Energy Explorer is a locally hosted web application for exploring
predicted electricity consumption across Forward Sortation Areas (FSAs).
It uses a React/Vite frontend, a FastAPI backend, and precomputed
Parquet predictions.

This guide explains how to clone the repository and run your own local
instance.

## 1. Requirements

Install the following before starting:

-   Git
-   Node.js 22 or newer, including npm
-   Python version supported by `energy-explorer/pyproject.toml`
-   [uv](https://docs.astral.sh/uv/) for Python environment and
    dependency management
-   The prediction Parquet file(s) used by the application

The prediction data may be stored separately from the Git repository.
Cloning the code does not necessarily download the Parquet dataset.

## 2. Clone the repository

Open a terminal and run:

``` bash
git clone --branch application_test https://github.com/DataholicsMDS27/temp_electricity.git
cd temp_electricity/energy-explorer
```

If you want to use a different branch, replace `application_test` with
that branch's name.

The commands below assume that the repository has this general layout:

``` text
temp_electricity/
├── data/
│   └── final_predictions_22-26/
└── energy-explorer/
    ├── backend/
    ├── src/
    ├── package.json
    └── pyproject.toml
```

## 3. Make the prediction data available

The backend needs one or more Parquet files containing the precomputed
predictions. The expected columns are:

-   `fsa`
-   `customer_type` (`1` = residential, `2` = business/commercial)
-   `day` (`0` = weekday, `1` = weekend/holiday)
-   `hour` (1--24)
-   `temperature` (−30 to 30)
-   `pred` (predicted consumption value)

Place the data somewhere accessible on the machine. If you keep the data
in the sibling folder shown above, set `ENERGY_PREDICTIONS_PARQUET` to
the path of the relevant file or files, according to the file-loading
behaviour of the checked-out `backend/parquet_predictor.py`.

**Important:** Do not assume the Parquet data is included in GitHub. If
you do not have access to it, obtain the dataset from the project owner
or configure the application to use a compatible dataset.

## 4. Start the backend

From the `energy-explorer` directory, create/install the Python
environment using the repository's `pyproject.toml` and lockfile:

``` bash
uv sync
```

Configure the predictor and the path to the Parquet file, then start the
API.

### Git Bash (Windows), macOS, or Linux

Run these commands in a dedicated terminal, adjusting the data filename
and path as needed:

``` bash
export ENERGY_PREDICTOR="backend.parquet_predictor:create_predictor"
export ENERGY_PREDICTIONS_PARQUET="../data/final_predictions_22-26/your_predictions.parquet"
uv run python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Replace `your_predictions.parquet` with the actual filename.

### Windows PowerShell

Use a separate PowerShell terminal:

``` powershell
$env:ENERGY_PREDICTOR = "backend.parquet_predictor:create_predictor"
$env:ENERGY_PREDICTIONS_PARQUET = "..\data\final_predictions_22-26\your_predictions.parquet"
uv run python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

The API should be available at `http://127.0.0.1:8000`. You can check
the metadata endpoint at:

``` text
http://127.0.0.1:8000/api/v1/metadata
```

Keep this terminal running.

## 5. Start the frontend

Open a second terminal in `temp_electricity/energy-explorer` and install
the JavaScript dependencies:

``` bash
npm ci
```

Then start the Vite development server:

``` bash
npm run dev
```

Open the local URL printed by Vite, typically:

``` text
http://127.0.0.1:5173/
```

Keep both the backend and frontend terminals running while using the
application.

## 6. Using the application

Use the controls to explore predictions by temperature, day type, hour,
and customer type. The map should update when the controls change. The
heatmap colour scale is intentionally capped to make typical values
easier to distinguish; values above the upper limit use the maximum
colour, while the underlying predictions remain unchanged.

## 7. Troubleshooting

### The map does not update or metadata fails

1.  Check that the backend terminal is still running.
2.  Open `http://127.0.0.1:8000/api/v1/metadata` and check for an error.
3.  Confirm that `ENERGY_PREDICTOR` is set to
    `backend.parquet_predictor:create_predictor`.
4.  Confirm that `ENERGY_PREDICTIONS_PARQUET` points to an existing
    Parquet file and that its columns match the schema above.

### The backend cannot find the Parquet file

The path is interpreted relative to the backend process's current
working directory. The commands in this guide start the backend from the
`energy-explorer` directory, so the example path begins with `../data/`.

### The frontend cannot connect to the backend

Make sure the backend is running on port `8000` and the frontend is
running on port `5173`. If the frontend is configured to use a different
API URL, check the relevant Vite environment configuration in the
repository.

### Dependencies fail to install

-   Check the installed Node.js version with `node --version`.
-   Check the Python version required by `pyproject.toml`.
-   Check that `uv` is installed with `uv --version`.
-   Use `npm ci` from the directory containing `package.json`.

## 8. Local development versus public hosting

These instructions run the application on your own computer; `127.0.0.1`
is only accessible from that computer. To make the app available to
other people over the internet, deploy the frontend and backend to
hosting services, configure the frontend to call the deployed API, allow
the required cross-origin requests, and provide the prediction data
securely to the backend. Do not expose a development server with
`--reload` directly to the public internet.

## License and data

Check the repository's license and the terms attached to the prediction
data before redistributing or publicly hosting the application or
dataset.
