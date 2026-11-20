import os
from pathlib import Path

import pytest
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from ground_ops.domain import Result
from ground_ops.instances import generate_assignment, generate_coverage
from ground_ops.model1 import build_model, solve_assignment
from ground_ops.model2 import solve_coverage
from ground_ops.progress import Progress, ProgressRecorder
from ground_ops.solver import gurobi_env
from ground_ops.telemetry import PROCESS_START, export_interval_ms, telemetry_from_environment
from tests.support import InMemoryTelemetry

METRIC_NAMES = {
    "groundops.solver.gap",
    "groundops.solver.incumbent",
    "groundops.solver.bound",
    "groundops.solver.incumbent_improvements",
    "groundops.solver.nodes",
    "groundops.solver.simplex_iterations",
    "groundops.solver.elapsed",
    "groundops.solver.work",
}


def exported(reader: InMemoryMetricReader) -> dict[str, list[tuple[dict[str, object], float]]]:
    data = reader.get_metrics_data()
    if data is None:
        return {}
    return {
        metric.name: [(dict(p.attributes or {}), p.value) for p in metric.data.data_points]  # type: ignore[union-attr]
        for rm in data.resource_metrics
        for sm in rm.scope_metrics
        for metric in sm.metrics
    }


@pytest.mark.parametrize(
    ("incumbent", "bound", "expected"),
    [(None, 5.0, None), (8.0, 8.0, 0.0), (10.0, 6.0, 0.4), (0.0, -2.0, None)],
)
def test_gap_is_relative_to_the_incumbent_and_undefined_without_one(
    incumbent: float | None, bound: float, expected: float | None
) -> None:
    assert Progress(0.0, 0.0, incumbent, bound, 0, 0, 0).gap == expected


def solve_both_ways(expose_search: bool) -> list[tuple[ProgressRecorder, Result]]:
    m1, m2 = ProgressRecorder("m1"), ProgressRecorder("m2")
    return [
        (m1, solve_assignment(generate_assignment(30, seed=1), recorder=m1, expose_search=expose_search)),
        (m2, solve_coverage(generate_coverage(seed=1), recorder=m2, expose_search=expose_search)),
    ]


@pytest.mark.parametrize("expose_search", [False, True])
def test_final_recorded_progress_equals_the_solve_result(expose_search: bool) -> None:
    # The last MIP callback can run before the final bound and incumbent, so this fails without recorder.finish.
    for recorder, result in solve_both_ways(expose_search):
        assert recorder.latest is not None
        assert recorder.latest.incumbent == result.objective
        assert recorder.latest.bound == result.bound
        assert recorder.latest.gap == result.gap
        assert recorder.latest.improvements >= 1


def test_final_recorded_nodes_and_iterations_equal_gurobis_own_counters() -> None:
    recorder = ProgressRecorder("x")
    with gurobi_env(expose_search=True) as env:
        model, _ = build_model(generate_assignment(30, seed=1), env)
        with model:
            model.optimize(recorder)
            recorder.finish(model)
            assert recorder.latest is not None
            assert recorder.latest.nodes == int(model.NodeCount)
            assert recorder.latest.iterations == int(model.IterCount)


def test_exposing_the_search_explores_nodes() -> None:
    recorder = ProgressRecorder("x")
    solve_assignment(generate_assignment(30, seed=1), recorder=recorder, expose_search=True)
    assert recorder.latest is not None
    assert recorder.latest.nodes > 1


def test_a_run_exports_every_metric_with_its_final_values_then_stops_being_reported(
    in_memory: InMemoryTelemetry,
) -> None:
    reader = in_memory.metrics
    with in_memory.telemetry.run("assignment") as recorder:
        result = solve_assignment(generate_assignment(30, seed=1), recorder=recorder, expose_search=True)

    metrics = exported(reader)
    assert set(metrics) == METRIC_NAMES
    labels = {"run_id": recorder.run_id, "model": "assignment"}
    assert metrics["groundops.solver.incumbent"] == [(labels, result.objective)]
    assert metrics["groundops.solver.bound"] == [(labels, result.bound)]
    assert metrics["groundops.solver.gap"] == [(labels, 0.0)]
    assert exported(reader) == {}


def test_run_ids_are_unique_and_start_with_the_process_start_time(in_memory: InMemoryTelemetry) -> None:
    ids = []
    for _ in range(3):
        with in_memory.telemetry.run("coverage") as recorder:
            ids.append(recorder.run_id)
    assert len(set(ids)) == 3
    assert all(i.startswith(f"{PROCESS_START}-{os.getpid()}-") for i in ids)


def test_exports_once_a_second_unless_the_interval_is_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_METRIC_EXPORT_INTERVAL", raising=False)
    assert export_interval_ms() == 1000
    monkeypatch.setenv("OTEL_METRIC_EXPORT_INTERVAL", "250")
    assert export_interval_ms() is None


def test_no_exporter_is_created_when_the_otlp_endpoint_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert telemetry_from_environment() is None


def test_a_log_file_is_written_and_nothing_goes_to_the_console(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "gurobi.log"
    solve_assignment(generate_assignment(30, seed=1), log_file=log, expose_search=True)
    assert "Expl Unexpl" in log.read_text()
    assert capfd.readouterr().out == ""


def test_a_run_traces_each_phase_under_one_root_span(in_memory: InMemoryTelemetry) -> None:
    with in_memory.telemetry.run("assignment") as recorder:
        solve_assignment(generate_assignment(10, seed=1), recorder=recorder)

    spans = {span.name: span for span in in_memory.spans.get_finished_spans()}
    assert set(spans) == {"ground-ops run", "build model", "solve"}
    root = spans["ground-ops run"]
    assert root.parent is None
    assert root.context is not None
    for name in ("build model", "solve"):
        parent = spans[name].parent
        assert parent is not None
        assert parent.span_id == root.context.span_id
    assert all(span.attributes is not None and span.attributes["run_id"] == recorder.run_id for span in spans.values())


def test_gurobi_log_lines_are_exported_with_the_run_id_and_trace(in_memory: InMemoryTelemetry) -> None:
    with in_memory.telemetry.run("coverage") as recorder:
        solve_coverage(generate_coverage(seed=1), recorder=recorder)

    root = next(s for s in in_memory.spans.get_finished_spans() if s.name == "ground-ops run")
    assert root.context is not None
    records = [data.log_record for data in in_memory.logs.get_finished_logs()]
    bodies = [str(r.body) for r in records]
    assert any(body.startswith("Optimal solution found") for body in bodies)
    assert all(r.attributes is not None and r.attributes["run_id"] == recorder.run_id for r in records)
    assert {r.trace_id for r in records} == {root.context.trace_id}
