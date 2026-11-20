"""Exports the progress of active solves as OpenTelemetry metrics."""

import itertools
import os
import time
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics import CallbackOptions, Observation
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import View
from opentelemetry.sdk.resources import Resource

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
    """Exports the progress of active solves as observable gauges, labelled by run id and model."""

    def __init__(self, reader: MetricReader) -> None:
        self._active: dict[tuple[str, str], ProgressRecorder] = {}
        self._provider = MeterProvider(
            resource=Resource.create({"service.name": "ground-ops"}),
            metric_readers=[reader],
            views=[View(instrument_name="groundops.solver.*", aggregation_cardinality_limit=RUN_CARDINALITY_LIMIT)],
        )
        meter = self._provider.get_meter("ground_ops")
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
        recorder = ProgressRecorder(f"{PROCESS_START}-{os.getpid()}-{next(_run_numbers)}")
        key = (recorder.run_id, model)
        self._active[key] = recorder
        try:
            yield recorder
        finally:
            self._provider.force_flush()
            del self._active[key]

    def shutdown(self) -> None:
        self._provider.shutdown()


def telemetry_from_environment() -> Telemetry | None:
    """OTLP export when OTEL_EXPORTER_OTLP_ENDPOINT is set; otherwise none, and no exporter is created."""
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return None
    return Telemetry(PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=export_interval_ms()))


def export_interval_ms() -> int | None:
    """None defers to OTEL_METRIC_EXPORT_INTERVAL when it's set."""
    # The SDK default is one export every 60 s, which turns a few-second solve into a single point.
    return None if os.environ.get("OTEL_METRIC_EXPORT_INTERVAL") else DEFAULT_EXPORT_INTERVAL_MS
