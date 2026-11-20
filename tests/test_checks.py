from ground_ops.checks import assignment_violations, total_overtime
from ground_ops.domain import AssignmentInstance, Handler, Task

INSTANCE = AssignmentInstance(
    tasks=(Task(0, 360, 380), Task(1, 370, 390), Task(2, 500, 520)),
    handlers=(Handler(0, 360, 480), Handler(1, 360, 600)),
)


def test_a_valid_assignment_has_no_violations() -> None:
    assert assignment_violations(INSTANCE, {0: 0, 1: 1, 2: 1}) == []


def test_reports_each_broken_rule() -> None:
    problems = assignment_violations(INSTANCE, {0: 0, 1: 0, 9: 5})
    assert problems == [
        "task 2 has no handler",
        "task 9 doesn't exist",
        "handler 5 doesn't exist",
        "handler 0 has conflicting tasks 0 and 1",
    ]


def test_total_overtime_sums_minutes_outside_each_shift() -> None:
    assert total_overtime(INSTANCE, {0: 0, 1: 1, 2: 0}) == 20
