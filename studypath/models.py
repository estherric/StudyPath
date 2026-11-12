"""Core data model

Time is split into one-hour study slots. 

A SchedulingProblem turns a start date, a weekly availability pattern and a list of tasks 
into an ordered list of slots, each tagged with the day (offset from the start date) it falls on. 

A Schedule assigns each slot to a task index, or None when the slot is left free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True)
class Task:
    """Something to study for: an assignment, exam or project.

    due       -- the task is due at the end of this date
    hours     -- estimated whole hours of work still needed
    priority  -- 1 (low) to 5 (high); scales lateness and missed-work cost
    difficulty-- 1 (easy) to 5 (hard); scales the cost of cramming on the due day
    """

    name: str
    due: date
    hours: int
    priority: int = 3
    difficulty: int = 3

    def __post_init__(self) -> None:
        if self.hours < 0:
            raise ValueError(f"{self.name}: hours must be >= 0")
        if not 1 <= self.priority <= 5:
            raise ValueError(f"{self.name}: priority must be 1-5")
        if not 1 <= self.difficulty <= 5:
            raise ValueError(f"{self.name}: difficulty must be 1-5")


@dataclass
class SchedulingProblem:
    """A scheduling problem that the AI will solve

    availability maps a weekday name ("Mon"..."Sun") to the hours free that day.
    
    late_days lets the planner keep scheduling for a few days after the last deadline
    so overdue work can still be finished (at a cost).
    """

    tasks: List[Task]
    start: date # The first day of the plan, user selected (usually "today")
    availability: Dict[str, int] # How many hours the user has free each day
    late_days: int = 2
    slot_days: List[int] = field(init=False)
    due_offsets: List[int] = field(init=False)

    def __post_init__(self) -> None:
        # Makes sure that only valid days are selected for availability
        for day in self.availability:
            if day not in WEEKDAYS:
                raise ValueError(f"unknown weekday {day!r}; use one of {WEEKDAYS}")
        
        # Sets the days offset from the start (start date = 0)
        self.due_offsets = [(t.due - self.start).days for t in self.tasks]
        last_day = max(self.due_offsets, default=-1) + self.late_days
        
        # slot_days contain the day numbers of each study hour and the position marks the hour
        # e.g. [0,0,1,2,2] means that (given that Monday is the start day) 
        # the student's first two free hours are on Monday (0), their 3rd free hour is on Tuesday (1), 
        # their 4th and 5th free hour is on Wednesday (2)
        self.slot_days = []
        for offset in range(0, last_day + 1):
            weekday = WEEKDAYS[(self.start + timedelta(days=offset)).weekday()]
            self.slot_days.extend([offset] * max(0, self.availability.get(weekday, 0)))

    @property
    def num_slots(self) -> int:
        return len(self.slot_days)

    def day_date(self, offset: int) -> date:
        return self.start + timedelta(days=offset)


@dataclass
class Schedule:
    """Result of a scheduler run - i.e. what is returned after the AI runs the SchedulingProblem
    through either A* or Greedy algorithm

    assignment[i] is the task index studied in slot i, or None if free.
    """

    problem: SchedulingProblem
    assignment: List[Optional[int]]
    algorithm: str
    expanded: int = 0
    optimal: bool = False # True only when A* proves that this is the most optimal plan
    runtime_s: float = 0.0

    def by_day(self) -> Dict[date, Dict[str, int]]:
        """Hours per task for each day, for display."""
        out: Dict[date, Dict[str, int]] = {}
        for slot, task_index in enumerate(self.assignment):
            if task_index is None:
                continue
            day = self.problem.day_date(self.problem.slot_days[slot])
            name = self.problem.tasks[task_index].name
            out.setdefault(day, {})
            out[day][name] = out[day].get(name, 0) + 1
        return out

    def printable(self) -> str:
        """Creates a printable text version"""
        lines = [f"{self.algorithm} schedule"]
        for day, hours in sorted(self.by_day().items()):
            parts = ", ".join(f"{name} {h}h" for name, h in hours.items())
            lines.append(f"  {day:%a %b %d}: {parts}")
        return "\n".join(lines)


def remaining_after(problem: SchedulingProblem, assignment: Sequence[Optional[int]]) -> List[int]:
    remaining = [t.hours for t in problem.tasks]
    for task_index in assignment:
        if task_index is not None:
            remaining[task_index] -= 1
    return remaining
