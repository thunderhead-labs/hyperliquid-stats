from prometheus_client import (
    Gauge,
    Counter,
    start_http_server,
    CollectorRegistry,
)
from prometheus_client.metrics import MetricWrapperBase

registry = CollectorRegistry()


def start_prometheus_server(port: int = 9000):
    try:
        start_http_server(port, registry=registry)
    except:
        print(
            f"Failed to start Prometheus exporter. Likely already running at this {port = }."
        )


def create_prometheus_labels(is_empty=False, **kwargs) -> dict:
    """
    Creates a Prometheus labels dictionary based on the key-value pairs provided as keyword arguments.

    Args:
        :param is_empty: A boolean indicating whether the labels dictionary values should be empty.
        **kwargs: Key-value pairs representing the label names and their corresponding values.

    Returns:
        A dictionary with the label names as keys and their corresponding values.

    Example:
        >>> create_prometheus_labels(app_name='blabla', node_id='0x1234', chain_id=1)
    """
    labels = {}
    for key, value in kwargs.items():
        if is_empty and not value:
            labels[key] = value
        elif isinstance(value, (str, int, float, bool)):
            labels[key] = str(value)
        else:
            raise TypeError(
                f"Label value for {key} must be a string, integer, float or boolean."
            )
    return labels


def create_metric(metric_name, metric_type, labels=None):
    if not labels:
        labels = []

    if metric_type == "gauge":
        metric = Gauge(
            metric_name,
            "",
            labelnames=labels,
            registry=registry,
            multiprocess_mode="livesum",
        )
    elif metric_type == "counter":
        metric = Counter(metric_name, "", labelnames=labels, registry=registry)
    else:
        raise ValueError(f"Invalid metric type: {metric_type}")

    return metric


def unregister_metric(metric: MetricWrapperBase):
    registry.unregister(metric)


def clear_metric(metric: MetricWrapperBase):
    metric.clear()


def unregister_label_metric(metric: MetricWrapperBase, label: str):
    metric.remove(label)


def export_metrics(metric, metric_value=None, labels=None):
    if labels:
        label_values = list(labels.values())
    else:
        label_values = []

    if metric_value is not None:
        if labels:
            if isinstance(metric, Gauge):
                metric.labels(*label_values).set(metric_value)
            elif isinstance(metric, Counter):
                metric.labels(*label_values).inc(metric_value)
            else:
                raise ValueError(f"Invalid metric type: {metric}")
        else:
            if isinstance(metric, Gauge):
                metric.set(metric_value)
            elif isinstance(metric, Counter):
                metric.inc(metric_value)
            else:
                raise ValueError(f"Invalid metric type: {metric}")
