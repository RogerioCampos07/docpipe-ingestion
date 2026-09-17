from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=['health'])


class LivenessResponse(BaseModel):
    """Response returned when the process is alive."""

    status: Literal['ok'] = 'ok'


@router.get('/health/live', response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    """Report process liveness without checking external dependencies."""
    return LivenessResponse()
