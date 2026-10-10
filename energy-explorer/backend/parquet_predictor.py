
"""Fast lookup provider for precomputed electricity predictions."""

import os
from pathlib import Path

import pandas as pd

from .schemas import Scenario


class ParquetPredictor:
    model_version = "precomputed-parquet-v1"
    is_mock = False

    def __init__(self, parquet_path: str | Path):
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

        df = pd.read_parquet(path, columns=columns)

        df["fsa"] = (
            df["fsa"].astype(str).str.strip().str.upper()
        )

        for col in [
            "customer_type",
            "day",
            "hour",
            "temperature",
        ]:
            df[col] = df[col].astype("int8")

        df["pred"] = pd.to_numeric(
            df["pred"], errors="raise"
        )

        if df["pred"].isna().any():
            raise ValueError(
                "The pred column contains missing values."
            )

        if not df["temperature"].between(-30, 30).all():
            raise ValueError(
                "Temperature must be between -30 and 30."
            )

        if not df["hour"].between(1, 24).all():
            raise ValueError(
                "Parquet hour must be between 1 and 24."
            )

        if not df["customer_type"].isin([1, 2]).all():
            raise ValueError(
                "customer_type must be 1 or 2."
            )

        if not df["day"].isin([0, 1]).all():
            raise ValueError(
                "day must be 0 or 1."
            )

        # Each scenario and FSA combination identifies one prediction.
        self.lookup = (
            df.set_index(
                [
                    "customer_type",
                    "day",
                    "hour",
                    "temperature",
                    "fsa",
                ]
            )["pred"]
            .sort_index()
        )

        self.supported_fsas = sorted(
            df["fsa"].unique().tolist()
        )

        self.pred_min = float(df["pred"].min())
        self.pred_max = float(df["pred"].max())

        del df

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

        try:
            values = self.lookup.loc[key]
        except KeyError as exc:
            raise ValueError(
                f"No predictions available for scenario {key}"
            ) from exc

        return [
            {
                "fsa": fsa,
                "value": (
                    float(values[fsa])
                    if fsa in values.index
                    else None
                ),
                "status": (
                    "ok"
                    if fsa in values.index
                    else "unsupported"
                ),
            }
            for fsa in fsa_codes
        ]


def create_predictor() -> ParquetPredictor:
    path = os.environ.get("ENERGY_PREDICTIONS_PARQUET")

    if not path:
        raise RuntimeError(
            "Set ENERGY_PREDICTIONS_PARQUET "
            "to the prediction Parquet path."
        )

    return ParquetPredictor(path)