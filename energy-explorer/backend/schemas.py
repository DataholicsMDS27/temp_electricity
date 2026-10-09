from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temperature_c: int = Field(ge=-40, le=35, strict=True)
    day_type: Literal["weekday", "weekend"]
    hour: int = Field(ge=0, le=23, strict=True)


class Prediction(BaseModel):
    fsa: str = Field(pattern=r"^[KLMNP][0-9][A-Z]$")
    value: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    status: Literal["ok", "unsupported", "unavailable"] = "ok"


class PredictionResponse(BaseModel):
    request_id: str
    scenario: Scenario
    model_version: str
    is_mock: bool
    boundary_version: str = "statcan-2021"
    metric: Literal["average_energy_per_customer"] = "average_energy_per_customer"
    unit: Literal["kWh"] = "kWh"
    interval_minutes: int = 60
    time_convention: str
    predictions: list[Prediction]
