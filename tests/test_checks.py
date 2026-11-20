from ground_ops.checks import assignment_violations, coverage_shortfalls, total_overtime, total_paid_slots
from ground_ops.domain import AssignmentInstance, CoverageInstance, Handler, ShiftPattern, Task

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


COVERAGE = CoverageInstance(
    demand=(1, 2, 1),
    patterns=(ShiftPattern(0, start=0, length=2, break_slot=None), ShiftPattern(1, start=1, length=2, break_slot=None)),
)


def test_enough_people_in_every_slot_has_no_shortfalls() -> None:
    assert coverage_shortfalls(COVERAGE, {0: 1, 1: 1}) == []


def test_reports_each_understaffed_slot_and_bad_pattern() -> None:
    assert coverage_shortfalls(COVERAGE, {0: 1, 1: -1, 7: 1}) == [
        "pattern 7 doesn't exist",
        "pattern 1 has -1 people",
        "slot 1 has 1 on duty, needs 2",
        "slot 2 has 0 on duty, needs 1",
    ]


def test_total_paid_slots_counts_people_times_paid_length() -> None:
    assert total_paid_slots(COVERAGE, {0: 2, 1: 1}) == 6
