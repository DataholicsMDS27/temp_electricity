"""Checks the Parquet-backed predictor against a tiny synthetic grid."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from .parquet_predictor import ParquetPredictor
from .schemas import Scenario


class ParquetPredictorTests(unittest.TestCase):
    def setUp(self):
        rows = [
            # fsa, customer_type, day, hour (1-24), temperature, pred
            ("M5V", 1, 0, 15, 22, 1.5),
            ("K1A", 1, 0, 15, 22, 2.5),
            ("M5V", 1, 0, 15, -30, 3.0),
            ("M5V", 2, 1, 1, 30, 4.0),
        ]
        frame = pd.DataFrame(rows, columns=["fsa", "customer_type", "day", "hour", "temperature", "pred"])
        frame["pred_raw"] = frame["pred"]
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / "grid.parquet"
        frame.to_parquet(path, index=False)
        self.predictor = ParquetPredictor(path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_lookup_converts_hour_and_day_codes(self):
        # API hour 14 is the 14:00-15:00 interval, stored as Parquet hour 15.
        rows = self.predictor.predict_batch(Scenario(temperature_c=22, day_type="weekday", hour=14), ["M5V", "K1A"])
        self.assertEqual([(r["fsa"], r["status"]) for r in rows], [("M5V", "ok"), ("K1A", "ok")])
        self.assertAlmostEqual(rows[0]["value"], 1.5)
        self.assertAlmostEqual(rows[1]["value"], 2.5)

    def test_temperature_extremes_and_customer_type(self):
        cold = self.predictor.predict_batch(Scenario(temperature_c=-30, day_type="weekday", hour=14), ["M5V"])
        self.assertAlmostEqual(cold[0]["value"], 3.0)
        business = self.predictor.predict_batch(
            Scenario(temperature_c=30, day_type="weekend", hour=0, customer_type=2), ["M5V"]
        )
        self.assertAlmostEqual(business[0]["value"], 4.0)

    def test_unknown_or_missing_fsa_is_unsupported(self):
        rows = self.predictor.predict_batch(Scenario(temperature_c=-30, day_type="weekday", hour=14), ["K1A", "ZZZ"])
        # K1A exists but has no value in this cell; ZZZ is not in the data at all.
        self.assertEqual([(r["value"], r["status"]) for r in rows], [(None, "unsupported")] * 2)

    def test_scenario_without_predictions_raises(self):
        with self.assertRaises(ValueError):
            self.predictor.predict_batch(Scenario(temperature_c=0, day_type="weekday", hour=3), ["M5V"])

    def test_missing_file_is_a_clear_error(self):
        with self.assertRaises(FileNotFoundError):
            ParquetPredictor("does-not-exist.parquet")


if __name__ == "__main__":
    unittest.main()
