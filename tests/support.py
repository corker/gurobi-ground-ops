from dataclasses import dataclass

from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from ground_ops.telemetry import Telemetry


@dataclass(frozen=True)
class InMemoryTelemetry:
    telemetry: Telemetry
    metrics: InMemoryMetricReader
    spans: InMemorySpanExporter
    logs: InMemoryLogRecordExporter
