"""How the final flush of a run gets slower as one process accumulates past runs (D21)."""

import statistics
import time

from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from ground_ops.progress import Progress
from ground_ops.telemetry import Telemetry

CHECKPOINTS = (100, 500, 1000, 2000, 4000)
WINDOW = 50


def main() -> None:
    telemetry = Telemetry(InMemoryMetricReader())
    timings: list[float] = []
    for _ in range(max(CHECKPOINTS)):
        start = time.perf_counter()
        with telemetry.run("assignment") as recorder:
            recorder.latest = Progress(0.0, 0.0, 1.0, 1.0, 0, 0, 1)
        timings.append((time.perf_counter() - start) * 1000)
    for checkpoint in CHECKPOINTS:
        window = timings[checkpoint - WINDOW : checkpoint]
        print(f"runs {checkpoint - WINDOW + 1}-{checkpoint}: median flush {statistics.median(window):.2f} ms")


if __name__ == "__main__":
    main()
