from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import BaseModel, ConfigDict

from ground_ops.telemetry import Telemetry


class InMemoryTelemetry(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    telemetry: Telemetry
    metrics: InMemoryMetricReader
    spans: InMemorySpanExporter
    logs: InMemoryLogRecordExporter
