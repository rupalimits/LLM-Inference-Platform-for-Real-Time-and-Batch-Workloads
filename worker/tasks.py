"""
Celery tasks for batch LLM inference.
The worker loads its own synchronous vLLM instance so it can run independently
of the FastAPI server (different pod / container).
"""
import logging
import time
import uuid
import os
from typing import List, Dict, Any

from celery import Task
from vllm import LLM, SamplingParams

from worker.celery_app import celery_app
from worker.metrics import BATCH_TASK_DURATION, BATCH_TOKENS_GENERATED

logger = logging.getLogger("worker")

MODEL_NAME = os.getenv("MODEL_NAME", "facebook/opt-125m")
TENSOR_PARALLEL_SIZE = int(os.getenv("TENSOR_PARALLEL_SIZE", "1"))
GPU_MEMORY_UTILIZATION = float(os.getenv("GPU_MEMORY_UTILIZATION", "0.90"))


class ModelTask(Task):
    """Base task that holds a singleton LLM instance (loaded once per worker process)."""

    _llm: LLM | None = None

    @property
    def llm(self) -> LLM:
        if self._llm is None:
            logger.info(f"Loading model {MODEL_NAME} in worker process")
            self._llm = LLM(
                model=MODEL_NAME,
                tensor_parallel_size=TENSOR_PARALLEL_SIZE,
                gpu_memory_utilization=GPU_MEMORY_UTILIZATION,
            )
            logger.info("Model loaded in worker")
        return self._llm


@celery_app.task(
    bind=True,
    base=ModelTask,
    name="worker.tasks.run_batch_inference",
    max_retries=2,
    default_retry_delay=30,
)
def run_batch_inference(
    self,
    prompts: List[str],
    max_tokens: int = 256,
    temperature: float = 0.7,
    top_p: float = 0.95,
) -> List[Dict[str, Any]]:
    """
    Run synchronous batch inference on a list of prompts.
    Returns a list of result dicts serialisable to JSON.
    """
    start = time.monotonic()
    sampling = SamplingParams(
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
    )

    try:
        outputs = self.llm.generate(prompts, sampling)
    except Exception as exc:
        logger.error(f"Batch inference failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)

    results = []
    total_tokens = 0
    for prompt, output in zip(prompts, outputs):
        completion = output.outputs[0]
        prompt_tokens = len(output.prompt_token_ids)
        completion_tokens = len(completion.token_ids)
        total_tokens += completion_tokens

        results.append(
            {
                "request_id": str(uuid.uuid4()),
                "prompt": prompt,
                "text": completion.text,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
        )

    duration = time.monotonic() - start
    BATCH_TASK_DURATION.observe(duration)
    BATCH_TOKENS_GENERATED.inc(total_tokens)

    logger.info(
        "batch complete",
        extra={
            "job_id": self.request.id,
            "num_prompts": len(prompts),
            "total_tokens": total_tokens,
            "duration_s": round(duration, 2),
        },
    )
    return results
