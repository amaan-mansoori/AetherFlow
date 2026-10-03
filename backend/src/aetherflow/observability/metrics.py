"""Small in-process Prometheus exposition and metrics abstraction."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from threading import Lock


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


@dataclass
class _Metric:
    name: str
    help: str
    label_names: tuple[str, ...]
    values: dict[tuple[str, ...], float] = field(default_factory=dict)

    def labels(self, labels: Mapping[str, str]) -> tuple[str, ...]:
        if set(labels) != set(self.label_names):
            raise ValueError(f"labels for {self.name} must be {self.label_names}")
        return tuple(str(labels[name]) for name in self.label_names)

    def label_text(self, key: tuple[str, ...]) -> str:
        if not key:
            return ""
        return (
            "{"
            + ",".join(
                f'{name}="{_escape(value)}"'
                for name, value in zip(self.label_names, key, strict=True)
            )
            + "}"
        )


class MetricsRegistry:
    """Thread-safe, bounded-label metrics registry."""

    def __init__(self) -> None:
        self._metrics: dict[str, _Metric] = {}
        self._lock = Lock()

    def counter(self, name: str, help_text: str, labels: tuple[str, ...] = ()) -> None:
        self._register(name, help_text, labels)

    def histogram(self, name: str, help_text: str, labels: tuple[str, ...] = ()) -> None:
        self._register(name, help_text, labels)

    def inc(self, name: str, value: float = 1.0, **labels: str) -> None:
        self._change(name, value, labels)

    def observe(self, name: str, value: float, **labels: str) -> None:
        self._change(f"{name}_sum", value, labels)
        self._change(f"{name}_count", 1, labels)

    def _register(self, name: str, help_text: str, labels: tuple[str, ...]) -> None:
        with self._lock:
            if name in self._metrics:
                return
            self._metrics[name] = _Metric(name, help_text, labels)
            if name.endswith("_seconds"):
                self._metrics[f"{name}_sum"] = _Metric(f"{name}_sum", help_text, labels)
                self._metrics[f"{name}_count"] = _Metric(f"{name}_count", help_text, labels)

    def _change(self, name: str, value: float, labels: Mapping[str, str]) -> None:
        with self._lock:
            metric = self._metrics.get(name)
            if metric is None:
                raise KeyError(f"metric is not registered: {name}")
            key = metric.labels(labels)
            metric.values[key] = metric.values.get(key, 0.0) + value

    def render(self) -> str:
        with self._lock:
            lines: list[str] = []
            for name, metric in self._metrics.items():
                if name.endswith("_sum") or name.endswith("_count"):
                    continue
                kind = "histogram" if name.endswith("_seconds") else "counter"
                lines.extend([f"# HELP {name} {metric.help}", f"# TYPE {name} {kind}"])
                for key, value in sorted(metric.values.items()):
                    lines.append(f"{name}{metric.label_text(key)} {value:g}")
                if kind == "histogram":
                    sum_metric = self._metrics[f"{name}_sum"]
                    count_metric = self._metrics[f"{name}_count"]
                    for key, value in sorted(sum_metric.values.items()):
                        lines.append(f"{name}_sum{sum_metric.label_text(key)} {value:g}")
                    for key, value in sorted(count_metric.values.items()):
                        lines.append(f"{name}_count{count_metric.label_text(key)} {value:g}")
            return "\n".join(lines) + "\n"


METRICS = MetricsRegistry()

_COUNTERS = {
    "aetherflow_http_requests_total": ("HTTP requests.", ("method", "route", "status_class")),
    "aetherflow_http_errors_total": ("HTTP errors.", ("method", "route", "status_class")),
    "aetherflow_jobs_created_total": ("Jobs created.", ("job_type",)),
    "aetherflow_jobs_completed_total": ("Jobs completed.", ("job_type",)),
    "aetherflow_jobs_failed_total": ("Jobs failed.", ("job_type", "failure_category")),
    "aetherflow_jobs_cancelled_total": ("Jobs cancelled.", ("job_type",)),
    "aetherflow_job_state_transitions_total": (
        "Job state transitions.",
        ("from_state", "to_state"),
    ),
    "aetherflow_worker_executions_started_total": ("Worker executions started.", ("job_type",)),
    "aetherflow_worker_executions_succeeded_total": ("Worker executions succeeded.", ("job_type",)),
    "aetherflow_worker_executions_failed_total": (
        "Worker executions failed.",
        ("job_type", "failure_category"),
    ),
    "aetherflow_worker_executions_retried_total": (
        "Worker executions retried.",
        ("job_type", "failure_category"),
    ),
    "aetherflow_worker_stale_messages_total": (
        "Stale or duplicate dispatch messages.",
        ("job_type",),
    ),
    "aetherflow_outbox_records_created_total": ("Outbox records created.", ()),
    "aetherflow_outbox_publish_attempts_total": ("Outbox publication attempts.", ()),
    "aetherflow_outbox_publications_succeeded_total": ("Outbox publications succeeded.", ()),
    "aetherflow_outbox_publications_failed_total": (
        "Outbox publications failed.",
        ("failure_category",),
    ),
    "aetherflow_retries_scheduled_total": ("Execution retries scheduled.", ("failure_category",)),
    "aetherflow_retries_exhausted_total": (
        "Execution retry budgets exhausted.",
        ("failure_category",),
    ),
    "aetherflow_provider_executions_total": ("Provider executions.", ("provider",)),
    "aetherflow_provider_successes_total": ("Provider successes.", ("provider",)),
    "aetherflow_provider_failures_total": ("Provider failures.", ("provider", "failure_category")),
    "aetherflow_redis_errors_total": ("Redis operation errors.", ("operation",)),
    "aetherflow_rate_limit_bypasses_total": ("Redis rate-limit bypasses.", ("rate_class",)),
    "aetherflow_rate_limit_requests_total": ("Rate-limited requests accepted.", ("rate_class",)),
    "aetherflow_rate_limit_blocked_total": ("Rate-limited requests blocked.", ("rate_class",)),
    "aetherflow_scheduled_jobs_created_total": ("Scheduled jobs created.", ()),
    "aetherflow_scheduled_jobs_due_total": ("Scheduled jobs activated when due.", ()),
    "aetherflow_scheduler_poll_cycles_total": ("Scheduler poll cycles.", ()),
    "aetherflow_scheduler_claims_total": ("Scheduler activation claims.", ()),
    "aetherflow_scheduler_claim_conflicts_total": ("Scheduler activation CAS conflicts.", ()),
    "aetherflow_scheduler_errors_total": ("Scheduler iteration errors.", ()),
    "aetherflow_scheduler_active_state_total": ("Scheduler lifecycle state changes.", ("state",)),
    "aetherflow_admin_operations_total": (
        "Administrative operations.",
        ("operation", "outcome"),
    ),
}
for _name, (_help, _labels) in _COUNTERS.items():
    METRICS.counter(_name, _help, _labels)
for _name, _help, _labels in (
    ("aetherflow_http_request_duration_seconds", "HTTP request duration.", ("method", "route")),
    ("aetherflow_worker_execution_duration_seconds", "Worker execution duration.", ("job_type",)),
    ("aetherflow_retry_delay_seconds", "Execution retry delay.", ("failure_category",)),
    (
        "aetherflow_provider_execution_duration_seconds",
        "Provider execution duration.",
        ("provider",),
    ),
    ("aetherflow_redis_operation_duration_seconds", "Redis operation duration.", ("operation",)),
    ("aetherflow_scheduler_lag_seconds", "Schedule activation lag.", ()),
):
    METRICS.histogram(_name, _help, _labels)
