"""The `ground-ops` command."""

import argparse
import sys

from ground_ops.domain import AssignmentInstance, Result, overtime
from ground_ops.instances import generate_assignment
from ground_ops.model1 import solve_assignment


def _clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _schedule_lines(instance: AssignmentInstance, result: Result) -> list[str]:
    lines = []
    for handler in instance.handlers:
        shift = f"{_clock(handler.shift_start)}-{_clock(handler.shift_end)}"
        tasks = sorted((t for t in instance.tasks if result.solution.get(t.id) == handler.id), key=lambda t: t.start)
        parts = []
        for t in tasks:
            extra = overtime(t, handler)
            parts.append(f"T{t.id} {_clock(t.start)}-{_clock(t.end)}" + (f" (+{extra} overtime)" if extra else ""))
        lines.append(f"H{handler.id} shift {shift}: " + (", ".join(parts) or "no tasks"))
    return lines


def report(instance: AssignmentInstance, seed: int, result: Result) -> str:
    """The text `ground-ops solve` prints for an optimal result."""
    header = f"Model 1: {len(instance.tasks)} tasks, {len(instance.handlers)} handlers, seed {seed}"
    summary = (
        f"status: {result.status}  overtime: {result.objective:g} min  "
        f"bound: {result.bound:g} min  gap: {(result.gap or 0.0) * 100:.2f}%"
    )
    return "\n".join([header, summary, *_schedule_lines(instance, result)])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ground-ops")
    commands = parser.add_subparsers(dest="command", required=True)
    solve = commands.add_parser("solve", help="solve a seeded Model 1 instance and print the schedule")
    solve.add_argument("--tasks", type=int, default=30, help="number of tasks, even (default: 30)")
    solve.add_argument("--seed", type=int, default=1, help="instance seed (default: 1)")
    args = parser.parse_args(argv)

    try:
        instance = generate_assignment(args.tasks, args.seed)
        result = solve_assignment(instance)
    except ValueError as error:
        print(f"ground-ops: {error}", file=sys.stderr)
        return 2
    print(report(instance, args.seed, result))
    return 0
