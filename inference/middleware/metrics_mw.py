import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# ── Prometheus metrics ──────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "inference_requests_total",
    "Total number of inference requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "inference_request_duration_seconds",
    "Inference request latency in seconds",
    ["endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

TOKENS_GENERATED = Counter(
    "inference_tokens_generated_total",
    "Total tokens generated",
    ["model"],
)

ACTIVE_REQUESTS = Gauge(
    "inference_active_requests",
    "Number of requests currently being processed",
)

BATCH_JOB_COUNT = Counter(
    "batch_jobs_total",
    "Total batch jobs submitted",
    ["status"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        ACTIVE_REQUESTS.inc()
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start
        ACTIVE_REQUESTS.dec()

        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
        ).inc()

        REQUEST_LATENCY.labels(endpoint=request.url.path).observe(duration)

        return response


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
