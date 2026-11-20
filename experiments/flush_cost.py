"""How the final flush of a run gets slower as one process accumulates past runs (D21)."""

import statistics
import time

from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from ground_ops.progress import Progress
from ground_ops.telemetry import Telemetry, new_run_id

CHECKPOINTS = (100, 500, 1000, 2000, 4000)
WINDOW = 50


def main() -> None:
    telemetry = Telemetry(
        InMemoryMetricReader(),
        SimpleSpanProcessor(InMemorySpanExporter()),
        SimpleLogRecordProcessor(InMemoryLogRecordExporter()),  # type: ignore[no-untyped-call]  # unannotated in the SDK
    )
    timings: list[float] = []
    for _ in range(max(CHECKPOINTS)):
        start = time.perf_counter()
        with telemetry.run("assignment", new_run_id()) as recorder:
            recorder.latest = Progress(
                elapsed=0.0, work=0.0, incumbent=1.0, bound=1.0, nodes=0, iterations=0, improvements=1
            )
        timings.append((time.perf_counter() - start) * 1000)
    for checkpoint in CHECKPOINTS:
        window = timings[checkpoint - WINDOW : checkpoint]
        print(f"runs {checkpoint - WINDOW + 1}-{checkpoint}: median flush {statistics.median(window):.2f} ms")


if __name__ == "__main__":
    main()
