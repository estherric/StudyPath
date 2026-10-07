# StudyPath

> An intelligent study-scheduling application that uses A* search to allocate study time across assignments, exams, and projects.

**StudyPath** is a CPSC 481 Artificial Intelligence project designed to help students create better study schedules based on their deadlines, workload, priorities, and weekly availability.

Rather than simply sorting assignments by due date, StudyPath models scheduling as a **state-space search problem** and uses **A* search with a custom heuristic** to explore possible schedules and recommend one that minimizes scheduling conflicts and unfinished work.

---

## Project Status

**Currently in development**

StudyPath is being developed as an 8-week team project for **CPSC 481: Artificial Intelligence**.

Current focus:

- [ ] Assignment input
- [ ] Weekly availability input
- [ ] Greedy scheduling baseline
- [ ] A* scheduling algorithm
- [ ] Custom heuristic
- [ ] Study schedule visualization
- [ ] Performance evaluation
- [ ] Final Streamlit application

---

## The Problem

Students often manage several courses at the same time, each with different:

- deadlines
- workloads
- priorities
- difficulty levels
- available study periods

A simple "do the closest assignment first" strategy does not always produce the best schedule.

For example, a small assignment due tomorrow may be less important than a major project due three days later that requires several hours of work.

StudyPath attempts to account for these competing factors when generating a study plan.

---

## Our Solution

Students provide:

- assignment or exam name
- due date
- estimated hours required
- priority
- difficulty
- weekly study availability

StudyPath then generates a recommended study schedule using two approaches:

### Greedy Scheduler

The baseline algorithm prioritizes tasks primarily by the nearest deadline.

### A* Scheduler

The primary AI algorithm explores possible schedules using:

```text
f(n) = g(n) + h(n)
```
where:
- g(n) = cost of the schedule created so far
- h(n) = estimated cost of the remaining unscheduled workload

In that case, the goal is to find a schedule with a lower overall scheduling cost.
