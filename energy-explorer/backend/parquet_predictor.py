
"""Fast lookup provider for precomputed electricity predictions."""

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .schemas import Scenario


class ParquetPredictor:
    model_version = "precomputed-parquet-v1"
    is_mock = False

    def __init__(self, parquet_path: str | Path):
        self.time_convention = "local"
        path = Path(parquet_path)

        if not path.is_file():
            raise FileNotFoundError(
                f"Prediction Parquet file not found: {path}"
            )

        columns = [
            "fsa",
            "customer_type",
            "day",
            "hour",
            "temperature",
            "pred",
        ]

        # Stream the file in batches so peak memory stays near the size of the
        # final grid rather than a full DataFrame copy (matters on small hosts).
        parquet = pq.ParquetFile(path)

        # First pass: scan the small key columns to size the grid.
        meta = pd.read_parquet(path, columns=["fsa", "temperature"], read_dictionary=["fsa"])
        names = sorted({str(n).strip().upper() for n in meta["fsa"].cat.categories})
        fsa_index = {fsa: i for i, fsa in enumerate(names)}
        temp_min, temp_max = int(meta["temperature"].min()), int(meta["temperature"].max())
        del meta
        if temp_min < -30 or temp_max > 30:
            raise ValueError("Temperature must be between -30 and 30.")

        grid = np.full(
            (3, 2, 25, temp_max - temp_min + 1, len(names)), np.nan, dtype="float32"
        )

        for batch in parquet.iter_batches(batch_size=250_000, columns=columns):
            df = batch.to_pandas()
            df["pred"] = pd.to_numeric(df["pred"], errors="raise")
            if df["pred"].isna().any():
                raise ValueError("The pred column contains missing values.")
            for col, allowed in (
                ("customer_type", [1, 2]),
                ("day", [0, 1]),
            ):
                if not df[col].isin(allowed).all():
                    raise ValueError(f"{col} must be one of {allowed}.")
            if not df["hour"].between(1, 24).all():
                raise ValueError("Parquet hour must be between 1 and 24.")

            fsa_codes = (
                df["fsa"].astype(str).str.strip().str.upper().map(fsa_index).to_numpy()
            )
            grid[
                df["customer_type"].to_numpy(dtype="int64"),
                df["day"].to_numpy(dtype="int64"),
                df["hour"].to_numpy(dtype="int64"),
                df["temperature"].to_numpy(dtype="int64") - temp_min,
                fsa_codes,
            ] = df["pred"].to_numpy(dtype="float32")

        self.supported_fsas = names
        self._fsa_index = fsa_index
        self._temp_min = temp_min
        self._grid = grid

        # Fixed colour scale to make typical consumption differences visible.
        self.pred_min = 0.0
        self.pred_max = 5.5


    def predict_batch(
        self,
        scenario: Scenario,
        fsa_codes: list[str],
    ) -> list[dict]:
        # Convert the frontend's readable day selection
        # into the numeric code used in the Parquet data.
        day = 0 if scenario.day_type == "weekday" else 1

        # Frontend hour is 0–23; Parquet hour is 1–24.
        data_hour = scenario.hour + 1

        key = (
            scenario.customer_type,
            day,
            data_hour,
            scenario.temperature_c,
        )

        temp_offset = scenario.temperature_c - self._temp_min
        if not 0 <= temp_offset < self._grid.shape[3]:
            raise ValueError(f"No predictions available for scenario {key}")

        values = self._grid[
            scenario.customer_type, day, data_hour, temp_offset
        ]
        if np.isnan(values).all():
            raise ValueError(f"No predictions available for scenario {key}")

        results = []
        for fsa in fsa_codes:
            i = self._fsa_index.get(fsa)
            value = None if i is None else float(values[i])
            if value is not None and np.isnan(value):
                value = None
            results.append(
                {
                    "fsa": fsa,
                    "value": value,
                    "status": "ok" if value is not None else "unsupported",
                }
            )
        return results

    def temperature_curve(
        self,
        day_type: str,
        hour: int,
        customer_type: int,
        fsa: str | None = None,
    ) -> list[tuple[int, float]]:
        """Predicted consumption at every temperature for one hour and day type.

        Without an FSA this is the unweighted mean across FSAs, a typical-FSA
        curve rather than a provincial total.
        """
        day = 0 if day_type == "weekday" else 1
        block = self._grid[customer_type, day, hour + 1]  # (temperatures, fsas)
        if fsa is not None:
            index = self._fsa_index.get(fsa.strip().upper())
            if index is None:
                raise KeyError(fsa)
            values = block[:, index]
        else:
            valid = ~np.isnan(block)
            counts = valid.sum(axis=1)
            sums = np.where(valid, block, 0.0).sum(axis=1)
            values = np.where(counts > 0, sums / np.maximum(counts, 1), np.nan)
        return [
            (self._temp_min + offset, float(value))
            for offset, value in enumerate(values)
            if not np.isnan(value)
        ]


def create_predictor() -> ParquetPredictor:
    path = os.environ.get("ENERGY_PREDICTIONS_PARQUET")

    if not path:
        raise RuntimeError(
            "Set ENERGY_PREDICTIONS_PARQUET "
            "to the prediction Parquet path."
        )

    return ParquetPredictor(path)