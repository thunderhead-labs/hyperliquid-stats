import inspect
import os
import time
from functools import wraps

from prom_utils import (
    create_metric,
    export_metrics,
    start_prometheus_server, create_prometheus_labels,
)

"""
Important notes:
Prometheus metrics are mainly used to constantly monitor the health of the system.
Due to the nature of our usage with chainflip, where many metrics are one time events,
or don't decrease and timeout by default, we need to implement some custom logic to handle this.

When integrating new metrics, please consider the following:
- If the metric is a one time event, please make sure to reset so alert won't fire forever.
- If the metric is constantly increasing, please make sure to reset so alert won't fire forever.
"""

PORT = os.getenv("PORT", 9000)
start_prometheus_server(PORT)

is_online = create_metric("is_hyperliquid_stats_online", "gauge")
api_latency = create_metric("hyperliquid_stats_api_latency", "gauge", labels=["endpoint"])
api_failures = create_metric("hyperliquid_stats_api_failures", "gauge", labels=["endpoint"])
api_successes = create_metric("hyperliquid_stats_api_successes", "gauge", labels=["endpoint"])


# Metric update methods
def update_is_online(value: bool = True):
    export_metrics(is_online, metric_value=int(value))


def update_api_latency(endpoint: str, latency: float):
    labels = create_prometheus_labels(endpoint=endpoint)
    export_metrics(api_latency, metric_value=latency, labels=labels)


def increment_api_failures(endpoint: str):
    api_failures.labels(endpoint).inc()


def increment_api_successes(endpoint: str):
    api_successes.labels(endpoint).inc()


# Helper decorators
def measure_api_latency(endpoint: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            increment_api_successes(endpoint)
            try:
                result = await func(*args, **kwargs)
                if inspect.iscoroutine(result):
                    result = await result
            except Exception as e:
                increment_api_failures(endpoint)
                print(f"Failed to resolve api {e}")
                return None
            latency = time.time() - start_time
            update_api_latency(endpoint, latency)
            return result

        return wrapper

    return decorator
