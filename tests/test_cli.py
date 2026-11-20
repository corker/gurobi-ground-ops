import pytest

from ground_ops.cli import main, report
from ground_ops.domain import AssignmentInstance, Handler, Result, Status, Task

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
