from pydantic import BaseModel, Field, StringConstraints
from typing import Annotated

from .states import TrialResult

SegmentCode = Annotated[str, StringConstraints(pattern=r'^[A-Z][0-9]{1,3}$')]
TrialCode = Annotated[str, StringConstraints(pattern=r'^[A-Z][A-Z0-9-]{2,23}$')]


class TrialInput(BaseModel):
    segment_code: SegmentCode
    slope_pct: float = Field(ge=0, le=20, allow_inf_nan=False)
    moisture_pct: float = Field(ge=0, le=100, allow_inf_nan=False)
    rut_mm: float = Field(ge=0, le=100, allow_inf_nan=False)
    observed_result: TrialResult | None = None


class OrderInput(BaseModel):
    retire_code: SegmentCode
    deploy_code: SegmentCode
    trial_code: TrialCode
    tide_window: str = Field(pattern=r'^([01][0-9]|2[0-3]):[0-5][0-9]–([01][0-9]|2[0-3]):[0-5][0-9]$')
    remarks: str = Field(default='', max_length=220)


class HandoverInput(BaseModel):
    recipient: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
