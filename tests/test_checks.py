from ground_ops.checks import assignment_violations, coverage_shortfalls, total_overtime, total_paid_slots
from ground_ops.domain import AssignmentInstance, CoverageInstance, Handler, ShiftPattern, Task

INSTANCE = AssignmentInstance(
    tasks=(Task(id=0, start=360, end=380), Task(id=1, start=370, end=390), Task(id=2, start=500, end=520)),
    handlers=(Handler(id=0, shift_start=360, shift_end=480), Handler(id=1, shift_start=360, shift_end=600)),
)


def test_a_valid_assignment_has_no_violations() -> None:
    assert assignment_violations(INSTANCE, assignment={0: 0, 1: 1, 2: 1}) == []


def test_reports_each_broken_rule() -> None:
    problems = assignment_violations(INSTANCE, assignment={0: 0, 1: 0, 9: 5})
    assert problems == [
        "task 2 has no handler",
        "task 9 doesn't exist",
        "handler 5 doesn't exist",
        "handler 0 has conflicting tasks 0 and 1",
    ]


def test_total_overtime_sums_minutes_outside_each_shift() -> None:
    assert total_overtime(INSTANCE, assignment={0: 0, 1: 1, 2: 0}) == 20


COVERAGE = CoverageInstance(
    demand=(1, 2, 1),
    patterns=(
        ShiftPattern(id=0, start=0, length=2, break_slot=None),
        ShiftPattern(id=1, start=1, length=2, break_slot=None),
    ),
)


def test_enough_people_in_every_slot_has_no_shortfalls() -> None:
    assert coverage_shortfalls(COVERAGE, staffing={0: 1, 1: 1}) == []


def test_reports_each_understaffed_slot_and_bad_pattern() -> None:
    assert coverage_shortfalls(COVERAGE, staffing={0: 1, 1: -1, 7: 1}) == [
        "pattern 7 doesn't exist",
        "pattern 1 has -1 people",
        "slot 1 has 1 on duty, needs 2",
        "slot 2 has 0 on duty, needs 1",
    ]


def test_total_paid_slots_counts_people_times_paid_length() -> None:
    assert total_paid_slots(COVERAGE, staffing={0: 2, 1: 1}) == 6
