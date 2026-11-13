"""A* search over partial study schedules.

Search state
    (slot, remaining, last)
    slot      -- index of the next free hour to fill
    remaining -- tuple of hours still needed per task
    last      -- task index used in the previous slot, if that slot was on the
                 same day; used to keep each day's tasks in index order

Within one day the order of study hours does not change the cost, so we only
generate each day's hours in non-decreasing task-index order. That turns every
permutation of a day's plan into one canonical plan and shrinks the search a lot.

Actions
    Study task j in this slot (any j with hours left, j >= last on the same day).
    Free slots are never generated: with the cost weights in cost.py, moving an
    hour of work into an earlier free slot never makes a schedule worse, so an
    optimal schedule exists that leaves no free slot while work remains.

Cost
    g(n) -- cost.slot_cost summed over the hours placed so far; when the slots
            run out, unfinished hours add the missed-work cost.
    h(n) -- see heuristic() below. It never overestimates, so A* returns an
            optimal schedule when it finishes within the expansion limit.
"""

from __future__ import annotations

import heapq
import itertools
import time
from typing import Dict, List, Optional, Tuple

from .cost import DEFAULT_WEIGHTS, CostWeights, slot_cost
from .models import SchedulingProblem, Schedule

State = Tuple[int, Tuple[int, ...], int]


class _Heuristic:
    """Admissible lower bound on the cost of finishing a partial schedule.

    It takes the largest of three bounds, each a lower bound on its own:

    1. Per task: hours of task j left beyond the free slots before j's due
       date must be late or missed, costing at least late * priority_j each.
       Summed over tasks (the hours are disjoint).
    2. Nested deadlines: for each due date D, all tasks due by D compete for
       the same slots, so any overflow is late or missed, costing at least
       late * (lowest priority among those tasks) each.
    3. Capacity: hours beyond all slots left are missed outright, costing at
       least missed * (lowest priority with hours left) each.
    """

    def __init__(self, problem: SchedulingProblem, w: CostWeights) -> None:
        self.p = problem
        self.w = w
        last_day = max(problem.slot_days, default=-1)
        horizon = max([last_day] + problem.due_offsets) + 1
        # upto[d] = number of slots on or before day d
        upto = [0] * max(horizon, 1)
        for d in problem.slot_days:
            upto[d] += 1
        for d in range(1, len(upto)):
            upto[d] += upto[d - 1]
        self.upto = upto
        self.by_due = sorted(range(len(problem.tasks)), key=lambda j: problem.due_offsets[j])
        self.prio = [t.priority for t in problem.tasks]

    def _slots_before(self, slot: int, day: int) -> int:
        if day < 0:
            return 0
        return max(0, self.upto[day] - slot)

    def __call__(self, slot: int, remaining: Tuple[int, ...]) -> float:
        w, p = self.w, self.p
        per_task = 0.0
        nested = 0.0
        need = 0
        min_prio = 6
        i = 0
        order = self.by_due
        while i < len(order):
            day = p.due_offsets[order[i]]
            # absorb every task sharing this due date
            while i < len(order) and p.due_offsets[order[i]] == day:
                j = order[i]
                r = remaining[j]
                if r:
                    cap = self._slots_before(slot, day)
                    if r > cap:
                        per_task += (r - cap) * w.late * self.prio[j]
                    need += r
                    min_prio = min(min_prio, self.prio[j])
                i += 1
            overflow = need - self._slots_before(slot, day)
            if overflow > 0:
                nested = max(nested, overflow * w.late * min_prio)
        total_left = p.num_slots - slot
        capacity = 0.0
        if need > total_left:
            capacity = (need - total_left) * w.missed * min_prio
        return max(per_task, nested, capacity)


def _missed_cost(problem: SchedulingProblem, remaining: Tuple[int, ...], w: CostWeights) -> float:
    return sum(w.missed * problem.tasks[j].priority * r for j, r in enumerate(remaining))


def astar_schedule(
    problem: SchedulingProblem,
    weights: CostWeights = DEFAULT_WEIGHTS,
    max_expansions: int = 200_000,
    h_weight: float = 1.0,
) -> Schedule:
    """Find a minimum-cost schedule with A*.

    h_weight > 1 runs weighted A* (faster, within h_weight of optimal).
    If max_expansions is hit, the most promising partial schedule found is
    finished with the greedy rule and the result is marked not optimal.
    """
    t0 = time.perf_counter()
    h = _Heuristic(problem, weights)
    n_slots = problem.num_slots
    days = problem.slot_days
    start_rem = tuple(t.hours for t in problem.tasks)
    start: State = (0, start_rem, 0)

    tie = itertools.count()
    # heap entries: (f, -slot, tiebreak, g, state, is_goal)
    frontier: List[tuple] = [(h_weight * h(0, start_rem), 0, next(tie), 0.0, start, False)]
    best_g: Dict[State, float] = {start: 0.0}
    parent: Dict[State, Tuple[Optional[State], Optional[int]]] = {start: (None, None)}
    expanded = 0
    last_popped = start

    def path_to(state: State) -> List[Optional[int]]:
        out: List[Optional[int]] = []
        while True:
            prev, task_idx = parent[state]
            if prev is None:
                break
            out.append(task_idx)
            state = prev
        out.reverse()
        return out

    def finish(state: State, optimal: bool) -> Schedule:
        assignment = path_to(state)
        assignment += [None] * (n_slots - len(assignment))
        return Schedule(
            problem=problem,
            assignment=assignment,
            algorithm="A*" if h_weight == 1.0 else f"Weighted A* (w={h_weight:g})",
            expanded=expanded,
            optimal=optimal and h_weight == 1.0,
            runtime_s=time.perf_counter() - t0,
        )

    while frontier:
        _f, _neg, _t, g, state, is_goal = heapq.heappop(frontier)
        if is_goal:
            return finish(state, optimal=True)
        if g > best_g.get(state, float("inf")):
            continue  # stale entry
        last_popped = state
        slot, remaining, last = state

        if slot == n_slots or not any(remaining):
            total = g + _missed_cost(problem, remaining, weights)
            heapq.heappush(frontier, (total, -slot, next(tie), total, state, True))
            continue

        expanded += 1
        if expanded > max_expansions:
            break

        same_day_next = slot + 1 < n_slots and days[slot + 1] == days[slot]
        for j in range(last, len(remaining)):
            if remaining[j] == 0:
                continue
            new_rem = remaining[:j] + (remaining[j] - 1,) + remaining[j + 1 :]
            child: State = (slot + 1, new_rem, j if same_day_next else 0)
            new_g = g + slot_cost(problem, slot, j, weights)
            if new_g < best_g.get(child, float("inf")):
                best_g[child] = new_g
                parent[child] = (state, j)
                f = new_g + h_weight * h(slot + 1, new_rem)
                heapq.heappush(frontier, (f, -(slot + 1), next(tie), new_g, child, False))

    # Expansion limit hit: finish the deepest promising partial plan greedily.
    prefix = path_to(last_popped)
    remaining = list(last_popped[1])
    order = sorted(
        range(len(problem.tasks)),
        key=lambda i: (problem.due_offsets[i], -problem.tasks[i].priority, i),
    )
    for _ in range(len(prefix), n_slots):
        pick = next((i for i in order if remaining[i] > 0), None)
        if pick is not None:
            remaining[pick] -= 1
        prefix.append(pick)
    sched = finish(last_popped, optimal=False)
    sched.assignment = prefix
    return sched
