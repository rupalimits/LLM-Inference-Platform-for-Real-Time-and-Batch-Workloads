from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Model
    model_name: str = "facebook/opt-125m"       # swap for any HF model id
    tensor_parallel_size: int = 1
    gpu_memory_utilization: float = 0.90
    max_model_len: Optional[int] = None

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    log_level: str = "info"

    # Redis / Celery
    redis_url: str = "redis://redis:6379/0"

    # Metrics
    metrics_port: int = 9090

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
