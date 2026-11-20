from pathlib import Path

import pytest

from ground_ops.cli import coverage_report, main, report
from ground_ops.domain import AssignmentInstance, CoverageInstance, Handler, Result, ShiftPattern, Status, Task
from tests.support import InMemoryTelemetry

INSTANCE = AssignmentInstance(
    tasks=(Task(0, 600, 615), Task(1, 420, 440), Task(2, 300, 320)),
    handlers=(Handler(0, 360, 600), Handler(1, 360, 600)),
)
RESULT = Result(Status.OPTIMAL, objective=60.0, bound=60.0, gap=0.0, solution={0: 0, 1: 0, 2: 0})


def test_report_lists_each_handlers_tasks_in_time_order_with_overtime() -> None:
    lines = report(INSTANCE, seed=4, result=RESULT).splitlines()
    assert lines == [
        "Model 1: 3 tasks, 2 handlers, seed 4",
        "status: optimal  overtime: 60 min  bound: 60 min  gap: 0.00%",
        "H0 shift 06:00-10:00: T2 05:00-05:20 (+20 overtime), T1 07:00-07:20, T0 10:00-10:15 (+15 overtime)",
        "H1 shift 06:00-10:00: no tasks",
    ]


def test_solve_command_prints_a_report_and_exits_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["solve", "--tasks", "10", "--seed", "3"]) == 0
    assert "status: optimal" in capsys.readouterr().out


def test_invalid_task_count_is_reported_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["solve", "--tasks", "7"]) == 2
    assert capsys.readouterr().err == "ground-ops: the task count must be a positive multiple of 2, got 7\n"


COVERAGE = CoverageInstance(
    demand=(1, 1, 1),
    patterns=(ShiftPattern(0, start=0, length=3, break_slot=None), ShiftPattern(1, start=1, length=1, break_slot=None)),
)
COVERAGE_RESULT = Result(Status.OPTIMAL, objective=4.0, bound=4.0, gap=0.0, solution={0: 1, 1: 1})


def test_coverage_report_shows_the_roster_and_demand_against_on_duty() -> None:
    assert coverage_report(COVERAGE, seed=2, result=COVERAGE_RESULT).splitlines() == [
        "Model 2: 3 half-hour slots, 2 shift patterns, seed 2",
        "status: optimal  cost: 4 paid half-hours  bound: 4 paid half-hours  gap: 0.00%",
        "roster:",
        "  1 x 00:00-01:30",
        "  1 x 00:30-01:00",
        "slot   demand  on duty",
        "00:00       1        1",
        "00:30       1        2  (+1)",
        "01:00       1        1",
    ]


def test_cover_command_prints_a_roster_and_exits_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["cover", "--seed", "1"]) == 0
    assert "status: optimal" in capsys.readouterr().out


def test_solve_exports_telemetry_and_names_the_run_when_a_collector_is_configured(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], in_memory: InMemoryTelemetry
) -> None:
    reader = in_memory.metrics
    monkeypatch.setattr("ground_ops.cli.telemetry_from_environment", lambda: in_memory.telemetry)
    assert main(["solve", "--tasks", "10", "--seed", "3"]) == 0
    assert "exporting telemetry for run_id" in capsys.readouterr().err
    data = reader.get_metrics_data()
    assert data is not None
    assert {m.name for m in data.resource_metrics[0].scope_metrics[0].metrics} >= {"groundops.solver.gap"}


def test_log_and_expose_search_options_write_a_log_with_a_search_tree(tmp_path: Path) -> None:
    log = tmp_path / "solve.log"
    assert main(["solve", "--tasks", "30", "--seed", "1", "--expose-search", "--log", str(log)]) == 0
    assert "Expl Unexpl" in log.read_text()


@pytest.mark.parametrize("command", ["solve", "cover"])
def test_a_log_in_a_missing_directory_is_refused_before_solving(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([command, "--log", "/nonexistent/dir/x.log"]) == 2
    assert capsys.readouterr().err == "ground-ops: can't write the log: /nonexistent/dir isn't a directory\n"


def test_the_cli_traces_instance_generation_too(monkeypatch: pytest.MonkeyPatch, in_memory: InMemoryTelemetry) -> None:
    monkeypatch.setattr("ground_ops.cli.telemetry_from_environment", lambda: in_memory.telemetry)
    assert main(["cover", "--seed", "2"]) == 0
    names = {span.name for span in in_memory.spans.get_finished_spans()}
    assert names == {"ground-ops run", "generate instance", "build model", "solve"}


def test_report_of_an_infeasible_result_lists_the_conflicting_constraints() -> None:
    infeasible = Result(Status.INFEASIBLE, None, None, None, {}, iis=("cover[0]", "no_overlap[h0,t0,t1]"))
    assert report(INSTANCE, seed=4, result=infeasible).splitlines() == [
        "Model 1: 3 tasks, 2 handlers, seed 4",
        "status: infeasible",
        "these constraints can't all hold, though any one fewer can (there may be other conflicts too):",
        "  cover[0]",
        "  no_overlap[h0,t0,t1]",
        "(cover[t]: task t needs one handler; no_overlap[hH,tA,tB]: handler H can't do both A and B)",
    ]


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (
            Result(Status.LIMIT_REACHED, objective=None, bound=None, gap=None, solution={}),
            "status: limit reached  no solution found  bound: none yet",
        ),
        (
            Result(Status.LIMIT_REACHED, objective=60.0, bound=None, gap=None, solution={0: 0, 1: 0, 2: 0}),
            "status: limit reached  overtime: 60 min  bound: none yet  gap: undefined",
        ),
        (
            Result(Status.LIMIT_REACHED, objective=60.0, bound=45.0, gap=0.25, solution={0: 0, 1: 0, 2: 0}),
            "status: limit reached  overtime: 60 min  bound: 45 min  gap: 25.00%",
        ),
    ],
)
def test_report_of_a_stopped_solve_shows_what_is_known(result: Result, expected: str) -> None:
    lines = report(INSTANCE, seed=4, result=result).splitlines()
    assert lines[1] == expected
    assert len(lines) == (2 if result.objective is None else 4)


def test_coverage_report_without_a_roster_shows_only_the_status() -> None:
    stopped = Result(Status.LIMIT_REACHED, objective=None, bound=3.0, gap=None, solution={})
    assert coverage_report(COVERAGE, seed=2, result=stopped).splitlines() == [
        "Model 2: 3 half-hour slots, 2 shift patterns, seed 2",
        "status: limit reached  no solution found  bound: 3 paid half-hours",
    ]


def test_too_few_handlers_prints_the_conflicting_constraints(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["solve", "--tasks", "10", "--seed", "1", "--handlers", "2"]) == 0
    out = capsys.readouterr().out
    assert "status: infeasible" in out
    assert "  cover[0]" in out


def test_work_limit_option_stops_the_solve_early(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["solve", "--tasks", "40", "--seed", "1", "--expose-search", "--work-limit", "0.5"]) == 0
    assert "status: limit reached" in capsys.readouterr().out


def test_a_negative_work_limit_is_reported_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["cover", "--work-limit", "-1"]) == 2
    assert "work limit must be zero or more" in capsys.readouterr().err
