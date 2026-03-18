import torch
from fastapi import APIRouter
from inference.models.schemas import HealthResponse
from inference.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model=settings.model_name,
        gpu_available=torch.cuda.is_available(),
    )


@router.get("/ready")
async def readiness():
    """Kubernetes readiness probe."""
    return {"ready": True}


@router.get("/live")
async def liveness():
    """Kubernetes liveness probe."""
    return {"live": True}
