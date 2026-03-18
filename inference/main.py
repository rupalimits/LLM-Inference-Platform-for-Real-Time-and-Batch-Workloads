"""
Cloud-Native LLM Inference Platform — FastAPI entry point.
"""
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from inference.config import settings
from inference.middleware.logging_mw import LoggingMiddleware, configure_logging
from inference.middleware.metrics_mw import MetricsMiddleware, metrics_response
from inference.routes import health, inference as inference_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load the vLLM engine
    from inference.routes.inference import init_engine
    init_engine()
    yield
    # Shutdown (nothing to do; vLLM cleans up internally)


configure_logging(settings.log_level)

app = FastAPI(
    title="LLM Inference Platform",
    description="Cloud-native, vLLM-backed inference API with async batch support.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware (order matters: added last = runs first) ───────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(MetricsMiddleware)
app.add_middleware(LoggingMiddleware)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(inference_router.router)


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return metrics_response()


if __name__ == "__main__":
    uvicorn.run(
        "inference.main:app",
        host=settings.host,
        port=settings.port,
        log_config=None,   # use our own JSON logger
    )
