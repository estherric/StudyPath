"""Schedule cost function shared by every scheduler.

Both the greedy baseline and A* are scored with the same function, so their
results are directly comparable. Costs, per hour of work:

  late      -- done after the due date: late * priority * days_late
  missed    -- never scheduled at all:  missed * priority
  cram      -- done on the due date itself: cram * difficulty
              (pushes hard tasks to start earlier)
  early     -- done before the due date: early * difficulty / (1 + days_early)
              (small, and shrinks the earlier the hour is done; it breaks ties
              between otherwise equal plans in favour of starting hard tasks
              sooner; with early / 2 <= cram it is always cheaper than cramming)

The weights must satisfy early / 2 <= cram, cram * 5 <= late and
late * (max days late) < missed for "always fill a free slot" to be a safe
assumption (doing an hour earlier must never cost more); the defaults do.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Sequence
from .models import SchedulingProblem

@dataclass(frozen=True)
class CostWeights:
    late: float = 10.0
    missed: float = 50.0
    cram: float = 1.0
    early: float = 0.2


DEFAULT_WEIGHTS = CostWeights()


def slot_cost(problem: SchedulingProblem, slot: int, task_index: int, w: CostWeights) -> float:
    """Cost of studying a task in the given slot."""
    task = problem.tasks[task_index]
    days_late = problem.slot_days[slot] - problem.due_offsets[task_index]
    if days_late > 0:
        return w.late * task.priority * days_late
    if days_late == 0:
        return w.cram * task.difficulty
    days_early = -days_late  # 1, 2, 3, ...
    return w.early * task.difficulty / (1 + days_early)


def evaluate(
    problem: SchedulingProblem, assignment: Sequence[Optional[int]], weights: CostWeights = DEFAULT_WEIGHTS) -> Dict[str, float]:
    """Break a schedule's cost into its parts, plus a few readable metrics."""
    late_cost = cram_cost = early_cost = 0.0
    late_hours = 0
    done = [0] * len(problem.tasks)
    finish_day = [None] * len(problem.tasks)
    for slot, task_index in enumerate(assignment):
        if task_index is None:
            continue
        done[task_index] += 1
        finish_day[task_index] = problem.slot_days[slot]
        c = slot_cost(problem, slot, task_index, weights)
        days_late = problem.slot_days[slot] - problem.due_offsets[task_index]
        if days_late > 0:
            late_cost += c
            late_hours += 1
        elif days_late == 0:
            cram_cost += c
        else:
            early_cost += c
    missed_hours = 0
    missed_cost = 0.0
    tasks_on_time = 0
    for i, task in enumerate(problem.tasks):
        short = task.hours - done[i]
        if short > 0:
            missed_hours += short
            missed_cost += weights.missed * task.priority * short
        elif finish_day[i] is None or finish_day[i] <= problem.due_offsets[i]:
            tasks_on_time += 1
    return {
        "total": late_cost + missed_cost + cram_cost + early_cost,
        "late_cost": late_cost,
        "missed_cost": missed_cost,
        "cram_cost": cram_cost,
        "early_cost": early_cost,
        "late_hours": late_hours,
        "missed_hours": missed_hours,
        "tasks_on_time": tasks_on_time,
        "tasks": len(problem.tasks),
    }
