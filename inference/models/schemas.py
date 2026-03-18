from pydantic import BaseModel, Field
from typing import Optional, List
import uuid


class InferenceRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Input prompt for the model")
    max_tokens: int = Field(default=256, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)
    stream: bool = Field(default=False)
    request_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))


class InferenceResponse(BaseModel):
    request_id: str
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float


class BatchInferenceRequest(BaseModel):
    prompts: List[str] = Field(..., min_items=1, max_items=100)
    max_tokens: int = Field(default=256, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)


class BatchJobResponse(BaseModel):
    job_id: str
    status: str
    num_prompts: int
    message: str


class BatchJobStatus(BaseModel):
    job_id: str
    status: str          # pending | processing | completed | failed
    num_prompts: int
    results: Optional[List[InferenceResponse]] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    model: str
    gpu_available: bool
    version: str = "1.0.0"
