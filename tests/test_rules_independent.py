"""The domain rules, re-implemented by counting minutes and slots, and compared on random seeded input.

The models, the checker and the brute-force tests all share the rule functions in domain.py, so a slip
there would pass every other test. These versions use a different method, so they don't share the slip.
"""

import random

from ground_ops.domain import GAP_MINUTES, Handler, ShiftPattern, Task, conflict, covers, overtime, paid_slots

CASES = 3000


def overtime_by_minutes(task: Task, *, handler: Handler) -> int:
    return sum(1 for minute in range(task.start, task.end) if not handler.shift_start <= minute < handler.shift_end)


def conflict_by_minutes(a: Task, *, b: Task) -> bool:
    """Each task blocks its handler from its start until the gap after it ends."""
    return bool(set(range(a.start, a.end + GAP_MINUTES)) & set(range(b.start, b.end + GAP_MINUTES)))


def on_duty_slots(pattern: ShiftPattern) -> set[int]:
    return set(range(pattern.start, pattern.start + pattern.length)) - {pattern.break_slot}


def random_task(rng: random.Random, *, task_id: int) -> Task:
    start = rng.randrange(0, 300)
    return Task(id=task_id, start=start, end=start + rng.randrange(0, 60))


def random_pattern(rng: random.Random) -> ShiftPattern:
    start, length = rng.randrange(0, 20), rng.randrange(1, 12)
    break_slot = rng.choice([None, start + rng.randrange(length)])
    return ShiftPattern(id=0, start=start, length=length, break_slot=break_slot)


def test_rules_agree_with_independent_counting() -> None:
    rng = random.Random(0)
    for case in range(CASES):
        a, b = random_task(rng, task_id=0), random_task(rng, task_id=1)
        shift_start = rng.randrange(0, 300)
        handler = Handler(id=0, shift_start=shift_start, shift_end=shift_start + rng.randrange(0, 200))
        pattern = random_pattern(rng)
        where = f"case {case}: {a}, {b}, {handler}, {pattern}"

        assert overtime(a, handler=handler) == overtime_by_minutes(a, handler=handler), where
        assert conflict(a, b=b) == conflict_by_minutes(a, b=b), where
        assert [s for s in range(40) if covers(pattern, slot=s)] == sorted(on_duty_slots(pattern)), where
        assert paid_slots(pattern) == len(on_duty_slots(pattern)), where
