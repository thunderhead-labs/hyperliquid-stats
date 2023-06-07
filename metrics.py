import inspect
import os
import time
from functools import wraps

from prom_utils import (
    create_metric,
    export_metrics,
    start_prometheus_server,
)

"""
Important notes:
Prometheus metrics are mainly used to constantly monitor the health of the system.
Due to the nature of our usage with chainflip, where many metrics are one time events,
or don't decrease and timeout by default, we need to implement some custom logic to handle this.

When integrating new metrics, please consider the following:
- If the metric is a one time event, please make sure to reset so alert won't fire forever.
- If the metric is constantly increasing, please make sure to reset so alert won't fire forever.


How to use:

1) Create the metrics you want to use with the create_metric function.
2) Export the metrics with the export_metrics function, you can create helper
    functions for specific metrics such as update_is_online.
3) In your service code start the prometheus server with the start_prometheus_server function.
4) Call the export_metrics or helper functions to update the metrics.
5) Reset metrics if needed with the clear_metric to reset completely or
    unregister_label_metric to reset only a specific label.

Helper functions:
There are 2 helper functions types defined here with different use cases.

1) Decorators such as measure_dependency_latency and measure_api_failures are used to wrap a function
    and perform certain operations around the decorated function.
    For example:
        @measure_dependency_latency("eth")
        def get_eth_data():
            ...

2) Regular functions such as update_is_online and update_is_synced are used to update the metrics.
    They can be called from anywhere in the code and chained together to update multiple metrics.
    For example:
        def get_eth_data():
            update_is_online("eth")
            ...

Reset logic:
Due to the nature of the metrics, some of them need to be reset after a certain amount of time.
Prometheus doesn't support this out of the box so we need to implement it ourselves.
The reset logic can be implemented in various ways but main ones are:
1) Reset the metric completely with the clear_metric function.
2) Reset only a specific label with the unregister_label_metric function.
    This is useful when you want to reset only a specific label and not the whole metric.
    This can be achieved with saving a in memory map that holds the last reset time / block for each label.
    Then when you want to reset a specific label you can check the last reset time and reset only if needed.
    Examples for the different approaches are in: reset_dependency_fails, reset_api_fails and reset_metrics.
"""

PORT = os.getenv("PORT", 9000)
start_prometheus_server(PORT)

is_online = create_metric("is_hyperliquid_stats_online", "gauge")
api_latency = create_metric("hyperliquid_stats_api_latency", "gauge")
api_failures = create_metric("hyperliquid_stats_api_failures", "gauge")

last_reset_api_failures = 0.0


# Metric update methods
def update_is_online(value: bool = True):
    export_metrics(is_online, metric_value=int(value))


def update_api_latency(latency: float):
    export_metrics(api_latency, metric_value=latency)


def increment_api_failures():
    api_failures.inc()


# Helper decorators
def measure_api_latency():
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            reset_api_fails()
            try:
                result = await func(*args, **kwargs)
                if inspect.iscoroutine(result):
                    result = await result
            except Exception as e:
                increment_api_failures()
                print(f"Failed to resolve api {e}")
                return None
            latency = time.time() - start_time
            update_api_latency(latency)
            return result

        return wrapper

    return decorator


def reset_api_fails():
    global last_reset_api_failures
    # Reset logic
    current_time = time.time()
    if current_time - last_reset_api_failures > 3600:
        api_failures.set(0)
        last_reset_api_failures = current_time
