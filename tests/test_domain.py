import pytest
from pydantic import BaseModel, ValidationError

from ground_ops.domain import Handler, ShiftPattern, Task, conflict, covers, overtime, paid_slots
from ground_ops.progress import Progress


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (Task, {"id": "3", "start": 360, "end": 400}),
        (Task, {"id": 3, "start": 360.0, "end": 400}),
        (Handler, {"id": True, "shift_start": 360, "shift_end": 600}),
        (
            Progress,
            {
                "elapsed": "1.0",
                "work": 0.0,
                "incumbent": None,
                "bound": None,
                "nodes": 0,
                "iterations": 0,
                "improvements": 0,
            },
        ),
    ],
)
def test_data_types_refuse_a_wrong_type_instead_of_converting_it(
    model: type[BaseModel], data: dict[str, object]
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_data_types_are_immutable() -> None:
    task = Task(id=0, start=360, end=400)
    with pytest.raises(ValidationError):
        task.start = 0


@pytest.mark.parametrize(
    ("second_start", "expected"),
    [
        (100, False),  # starts exactly 10 minutes after the first ends: allowed
        (99, True),  # 9 minutes: too close
        (80, True),  # overlapping
    ],
)
def test_conflict_respects_the_ten_minute_gap(second_start: int, expected: bool) -> None:
    first = Task(id=0, start=60, end=90)
    second = Task(id=1, start=second_start, end=second_start + 20)
    assert conflict(first, b=second) is expected
    assert conflict(second, b=first) is expected


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (400, 420, 0),  # inside the shift
        (350, 370, 10),  # starts 10 minutes before the shift
        (590, 610, 10),  # ends 10 minutes after the shift
        (300, 320, 20),  # entirely before
        (350, 610, 20),  # spans the whole shift, 10 minutes each side
    ],
)
def test_overtime_counts_minutes_outside_the_shift(start: int, end: int, expected: int) -> None:
    handler = Handler(id=0, shift_start=360, shift_end=600)
    assert overtime(Task(id=0, start=start, end=end), handler=handler) == expected


def test_a_pattern_covers_its_slots_except_the_break() -> None:
    pattern = ShiftPattern(id=0, start=4, length=4, break_slot=6)
    assert [s for s in range(10) if covers(pattern, slot=s)] == [4, 5, 7]


@pytest.mark.parametrize(("break_slot", "expected"), [(None, 8), (5, 7)])
def test_the_break_is_unpaid(break_slot: int | None, expected: int) -> None:
    assert paid_slots(ShiftPattern(id=0, start=2, length=8, break_slot=break_slot)) == expected
