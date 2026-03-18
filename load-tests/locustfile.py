"""
Locust load test for the LLM Inference Platform.

Run:
    locust -f locustfile.py --host http://localhost:8000 \
           --users 20 --spawn-rate 2 --run-time 2m \
           --csv=results/locust --headless

Then generate the latency report:
    python generate_report.py --csv-prefix results/locust
"""
import json
import random
from locust import HttpUser, task, between, events

SAMPLE_PROMPTS = [
    "Explain quantum computing in simple terms.",
    "Write a Python function to sort a list of dictionaries by a key.",
    "What are the main causes of the French Revolution?",
    "Summarise the theory of relativity in three sentences.",
    "How does a transformer neural network work?",
    "Give me a recipe for a vegan chocolate cake.",
    "What is the difference between TCP and UDP?",
    "Write a haiku about machine learning.",
    "Explain the concept of gradient descent.",
    "What are SOLID principles in software engineering?",
]


class InferenceUser(HttpUser):
    """Simulates a user hitting the real-time inference endpoint."""

    wait_time = between(0.5, 2.0)   # think time between requests

    @task(5)
    def realtime_inference(self):
        payload = {
            "prompt": random.choice(SAMPLE_PROMPTS),
            "max_tokens": random.randint(64, 256),
            "temperature": round(random.uniform(0.5, 1.0), 2),
        }
        with self.client.post(
            "/v1/inference",
            json=payload,
            headers={"Content-Type": "application/json"},
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}: {resp.text[:200]}")

    @task(1)
    def batch_submit(self):
        """Submit a small batch job (fire-and-forget for throughput testing)."""
        payload = {
            "prompts": random.sample(SAMPLE_PROMPTS, k=random.randint(2, 5)),
            "max_tokens": 128,
        }
        with self.client.post(
            "/v1/batch",
            json=payload,
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}: {resp.text[:200]}")

    @task(1)
    def health_check(self):
        self.client.get("/health")


class StreamingUser(HttpUser):
    """Simulates a user hitting the streaming endpoint."""

    wait_time = between(1.0, 3.0)
    weight = 1   # fewer streaming users than regular

    @task
    def streaming_inference(self):
        payload = {
            "prompt": random.choice(SAMPLE_PROMPTS),
            "max_tokens": 128,
            "stream": True,
        }
        with self.client.post(
            "/v1/inference/stream",
            json=payload,
            stream=True,
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                # consume the SSE stream
                for _ in resp.iter_lines():
                    pass
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")


# ── Event hooks ───────────────────────────────────────────────────────────────
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kw):
    """Custom listener — can write to a file or push to external systems."""
    pass


@events.quitting.add_listener
def on_quitting(environment, **kw):
    if environment.stats.total.fail_ratio > 0.05:
        print(f"[WARN] Error rate {environment.stats.total.fail_ratio:.1%} exceeds 5%")
