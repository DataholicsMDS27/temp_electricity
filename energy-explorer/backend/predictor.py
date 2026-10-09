"""Model integration boundary. Replace this provider, not the HTTP contract.

Set ENERGY_PREDICTOR=your_package:create_predictor to load a real provider.
The factory takes no arguments and returns an object implementing Predictor.
Bundle preprocessing, static FSA features and dependencies with your provider.
"""
import hashlib
import math
from typing import Protocol
from .schemas import Scenario, Prediction


class Predictor(Protocol):
    model_version: str
    is_mock: bool
    time_convention: str

    def predict_batch(self, scenario: Scenario, fsa_codes: list[str]) -> list[Prediction]: ...


class MockPredictor:
    model_version = "synthetic-demo-v1"
    is_mock = True
    time_convention = "Typical local hour; timezone convention pending model integration"

    def predict_batch(self, scenario: Scenario, fsa_codes: list[str]) -> list[Prediction]:
        """Deterministic illustrative values. Not fitted to consumption observations."""
        hour = scenario.hour
        morning = math.exp(-((hour - 8) / 2.5) ** 2)
        evening = math.exp(-((hour - 19) / 3) ** 2)
        weather = max(0, 15 - scenario.temperature_c) * 0.028 + max(0, scenario.temperature_c - 22) * 0.055
        day_factor = 1.08 if scenario.day_type == "weekend" else 1.0
        result = []
        for fsa in fsa_codes:
            stable = int(hashlib.sha256(fsa.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
            geographic_factor = 0.72 + stable * 0.65
            value = (0.65 + 0.32 * morning + 0.68 * evening + weather) * geographic_factor * day_factor
            result.append(Prediction(fsa=fsa, value=round(value, 3), status="ok"))
        return result
