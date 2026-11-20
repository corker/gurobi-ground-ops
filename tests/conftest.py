from collections.abc import Iterator

import pytest
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from ground_ops.telemetry import Telemetry
from tests.support import InMemoryTelemetry


@pytest.fixture
def in_memory() -> Iterator[InMemoryTelemetry]:
    # The SDK's InMemoryLogRecordExporter has no type annotations (opentelemetry-sdk 1.45.2).
    logs = InMemoryLogRecordExporter()  # type: ignore[no-untyped-call]
    metrics, spans = InMemoryMetricReader(), InMemorySpanExporter()
    telemetry = Telemetry(metrics, spans=SimpleSpanProcessor(spans), logs=SimpleLogRecordProcessor(logs))
    yield InMemoryTelemetry(telemetry=telemetry, metrics=metrics, spans=spans, logs=logs)
    telemetry.shutdown()
