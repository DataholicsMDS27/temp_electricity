"""Smoke-test a configured trained provider through the actual HTTP contract.

ENERGY_PREDICTOR=backend.model_provider:create_predictor \
  .venv/bin/python -m backend.check_model
"""

import os

from fastapi.testclient import TestClient

from .main import app


def main():
    if not os.getenv("ENERGY_PREDICTOR"):
        raise SystemExit("Set ENERGY_PREDICTOR to the trained provider factory; demo mode is not a model integration test.")
    with TestClient(app) as client:
        health = client.get("/api/health")
        health.raise_for_status()
        metadata_response = client.get("/api/v1/metadata")
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        assert metadata["is_mock"] is False, "Expected a trained provider"
        assert metadata["time_convention"], "Document the training time convention"
        expected = set(metadata["supported_fsas"])
        scenarios = 0
        for temperature in (-40, 0, 22, 35):
            for day_type in ("weekday", "weekend"):
                for hour in (0, 6, 14, 18, 23):
                    scenario = {"temperature_c": temperature, "day_type": day_type, "hour": hour}
                    response = client.post("/api/v1/predictions", json=scenario)
                    response.raise_for_status()
                    result = response.json()
                    assert result["scenario"] == scenario
                    assert result["is_mock"] is False
                    assert result["unit"] == "kWh" and result["interval_minutes"] == 60
                    assert result["metric"] == "average_energy_per_customer"
                    assert result["model_version"] == metadata["model_version"]
                    rows = result["predictions"]
                    assert len(rows) == len(expected)
                    assert {row["fsa"] for row in rows} == expected
                    valid = [row for row in rows if row["status"] == "ok"]
                    assert valid, f"No usable predictions for {scenario}"
                    assert all(row["value"] is None for row in rows if row["status"] != "ok")
                    scenarios += 1
        invalid = client.post("/api/v1/predictions", json={"temperature_c": 36, "day_type": "weekday", "hour": 14})
        assert invalid.status_code == 422
        print(f"Model {metadata['model_version']}: {scenarios} scenarios passed across {len(expected)} map FSAs.")
        print("This verifies integration, not predictive accuracy. Evaluate a held-out dataset separately.")


if __name__ == "__main__":
    main()
