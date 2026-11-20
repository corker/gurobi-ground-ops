"""Exports each solve as OpenTelemetry signals: progress metrics, a trace with a span per phase, and Gurobi's log.

The logs SDK is still in Development status for Python (https://opentelemetry.io/docs/languages/python/),
which is why its modules are underscore-prefixed; traces and metrics are stable.
"""

import itertools
import os
import time
from collections.abc import Callable, Iterable, Iterator
from contextlib import AbstractContextManager, contextmanager

from opentelemetry._logs import SeverityNumber
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.metrics import CallbackOptions, Observation
from opentelemetry.sdk._logs import LoggerProvider, LogRecordProcessor
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from ground_ops.progress import Progress, ProgressRecorder

PROCESS_START = int(time.time())
_run_numbers = itertools.count(1)
# The SDK keeps every attribute set it has seen, so a long-lived process would hit the default cap of 2000 runs.
RUN_CARDINALITY_LIMIT = 100_000
DEFAULT_EXPORT_INTERVAL_MS = 1000

type Observer = Callable[[CallbackOptions], Iterable[Observation]]


METRICS: tuple[tuple[str, str, Callable[[Progress], float | None]], ...] = (
    ("gap", "1", lambda p: p.gap),
    ("incumbent", "{objective}", lambda p: p.incumbent),
    ("bound", "{objective}", lambda p: p.bound),
    ("incumbent_improvements", "{solution}", lambda p: p.improvements),
    ("nodes", "{node}", lambda p: p.nodes),
    ("simplex_iterations", "{iteration}", lambda p: p.iterations),
    ("elapsed", "s", lambda p: p.elapsed),
    ("work", "{work_unit}", lambda p: p.work),
)


class Telemetry:
    """Exports each run's progress gauges, phase spans and Gurobi log lines, all labelled by run id and model."""

    def __init__(self, metrics: MetricReader, spans: SpanProcessor, logs: LogRecordProcessor) -> None:
        self._active: dict[tuple[str, str], ProgressRecorder] = {}
        resource = Resource.create({"service.name": "ground-ops"})
        self._meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metrics],
            views=[View(instrument_name="groundops.solver.*", aggregation_cardinality_limit=RUN_CARDINALITY_LIMIT)],
        )
        self._tracer_provider = TracerProvider(resource=resource)
        self._tracer_provider.add_span_processor(spans)
        self._logger_provider = LoggerProvider(resource=resource)
        self._logger_provider.add_log_record_processor(logs)
        self._tracer = self._tracer_provider.get_tracer("ground_ops")
        self._logger = self._logger_provider.get_logger("ground_ops.gurobi")
        meter = self._meter_provider.get_meter("ground_ops")
        for name, unit, value in METRICS:
            meter.create_observable_gauge(f"groundops.solver.{name}", callbacks=[self._observer(value)], unit=unit)

    def _observer(self, value: Callable[[Progress], float | None]) -> Observer:
        def observe(_: CallbackOptions) -> Iterable[Observation]:
            for (run_id, model), recorder in list(self._active.items()):
                if recorder.latest is not None and (v := value(recorder.latest)) is not None:
                    yield Observation(v, {"run_id": run_id, "model": model})

        return observe

    @contextmanager
    def run(self, model: str) -> Iterator[ProgressRecorder]:
        """Report a solve while it runs. The final values are flushed before the run stops being reported."""
        run_id = f"{PROCESS_START}-{os.getpid()}-{next(_run_numbers)}"
        labels = {"run_id": run_id, "model": model}

        def start_span(name: str) -> AbstractContextManager[object]:
            return self._tracer.start_as_current_span(name, attributes=labels)

        def on_log_line(line: str) -> None:
            self._logger.emit(body=line, attributes=labels, severity_number=SeverityNumber.INFO)

        recorder = ProgressRecorder(run_id, start_span=start_span, on_log_line=on_log_line)
        key = (run_id, model)
        try:
            with self._tracer.start_as_current_span("ground-ops run", attributes=labels):
                self._active[key] = recorder
                try:
                    yield recorder
                finally:
                    self._meter_provider.force_flush()
                    del self._active[key]
        finally:
            self._tracer_provider.force_flush()
            self._logger_provider.force_flush()

    def shutdown(self) -> None:
        self._meter_provider.shutdown()
        self._tracer_provider.shutdown()
        self._logger_provider.shutdown()


def telemetry_from_environment() -> Telemetry | None:
    """OTLP export when OTEL_EXPORTER_OTLP_ENDPOINT is set; otherwise none, and no exporter is created."""
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return None
    return Telemetry(
        PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=export_interval_ms()),
        BatchSpanProcessor(OTLPSpanExporter()),
        BatchLogRecordProcessor(OTLPLogExporter()),
    )


def export_interval_ms() -> int | None:
    """None defers to OTEL_METRIC_EXPORT_INTERVAL when it's set."""
    # The SDK default is one export every 60 s, which turns a few-second solve into a single point.
    return None if os.environ.get("OTEL_METRIC_EXPORT_INTERVAL") else DEFAULT_EXPORT_INTERVAL_MS
