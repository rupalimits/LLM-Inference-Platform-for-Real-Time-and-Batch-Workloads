import time
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from vllm import LLM, SamplingParams
from vllm.engine.arg_utils import AsyncEngineArgs
from vllm.engine.async_llm_engine import AsyncLLMEngine

from inference.models.schemas import (
    InferenceRequest,
    InferenceResponse,
    BatchInferenceRequest,
    BatchJobResponse,
)
from inference.middleware.metrics_mw import TOKENS_GENERATED, BATCH_JOB_COUNT
from inference.config import settings

logger = logging.getLogger("inference")
router = APIRouter(tags=["Inference"])

# ── Engine (loaded once at startup via lifespan) ─────────────────────────────
_engine: AsyncLLMEngine | None = None


def get_engine() -> AsyncLLMEngine:
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not initialised")
    return _engine


def init_engine() -> None:
    global _engine
    logger.info("Loading model", extra={"model": settings.model_name})
    engine_args = AsyncEngineArgs(
        model=settings.model_name,
        tensor_parallel_size=settings.tensor_parallel_size,
        gpu_memory_utilization=settings.gpu_memory_utilization,
        max_model_len=settings.max_model_len,
    )
    _engine = AsyncLLMEngine.from_engine_args(engine_args)
    logger.info("Model loaded successfully")


# ── Real-time inference ───────────────────────────────────────────────────────
@router.post("/v1/inference", response_model=InferenceResponse)
async def inference(req: InferenceRequest, request: Request) -> InferenceResponse:
    engine = get_engine()
    sampling = SamplingParams(
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        top_p=req.top_p,
    )

    start = time.monotonic()
    results = []
    async for output in engine.generate(req.prompt, sampling, req.request_id):
        results.append(output)

    final = results[-1]
    completion = final.outputs[0]
    latency_ms = round((time.monotonic() - start) * 1000, 2)

    prompt_tokens = len(final.prompt_token_ids)
    completion_tokens = len(completion.token_ids)

    TOKENS_GENERATED.labels(model=settings.model_name).inc(completion_tokens)

    logger.info(
        "inference complete",
        extra={
            "request_id": req.request_id,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": latency_ms,
        },
    )

    return InferenceResponse(
        request_id=req.request_id,
        text=completion.text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        latency_ms=latency_ms,
    )


# ── Streaming inference ───────────────────────────────────────────────────────
@router.post("/v1/inference/stream")
async def inference_stream(req: InferenceRequest):
    engine = get_engine()
    sampling = SamplingParams(
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        top_p=req.top_p,
    )

    async def token_generator() -> AsyncGenerator[str, None]:
        prev_text = ""
        async for output in engine.generate(req.prompt, sampling, req.request_id):
            new_text = output.outputs[0].text
            delta = new_text[len(prev_text):]
            prev_text = new_text
            if delta:
                yield f"data: {delta}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(token_generator(), media_type="text/event-stream")


# ── Batch submission (offloads to Celery) ─────────────────────────────────────
@router.post("/v1/batch", response_model=BatchJobResponse)
async def submit_batch(req: BatchInferenceRequest) -> BatchJobResponse:
    # Import here to avoid circular dependency at module load time
    from worker.tasks import run_batch_inference

    task = run_batch_inference.delay(
        prompts=req.prompts,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        top_p=req.top_p,
    )
    BATCH_JOB_COUNT.labels(status="submitted").inc()
    logger.info("batch job submitted", extra={"job_id": task.id, "num_prompts": len(req.prompts)})

    return BatchJobResponse(
        job_id=task.id,
        status="pending",
        num_prompts=len(req.prompts),
        message="Batch job queued successfully",
    )


@router.get("/v1/batch/{job_id}")
async def get_batch_status(job_id: str):
    from celery.result import AsyncResult
    from worker.celery_app import celery_app

    result = AsyncResult(job_id, app=celery_app)
    state = result.state

    if state == "PENDING":
        return {"job_id": job_id, "status": "pending"}
    elif state == "SUCCESS":
        return {"job_id": job_id, "status": "completed", "results": result.result}
    elif state == "FAILURE":
        return {"job_id": job_id, "status": "failed", "error": str(result.result)}
    else:
        return {"job_id": job_id, "status": state.lower()}
