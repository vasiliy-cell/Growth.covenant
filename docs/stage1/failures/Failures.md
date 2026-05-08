# Failures, Mistakes, and Architectural Lessons

This document collects some of the most important mistakes, failed ideas, confusing moments, and unexpected behaviors encountered during Stage 1.

The purpose of this file is not just to list bugs, but to document:

* architectural lessons
* reinforcement learning pitfalls
* debugging insights
* design tradeoffs
* unexpected emergent behavior

A large part of building learning systems is not “making things work”, but understanding *why* they fail.

---

# Almost Passing the Entire World Into the Brain

## Problem

An early architectural idea was to directly pass the entire map into the brain.

At first this seemed logical:

> the agent “sees” the world, so why not provide everything?

But this would have created:

* tight coupling
* direct dependency between brain and environment
* poor scalability
* difficult future replacement of systems

---

## Why It Was Dangerous

This would have broken one of the main architectural goals:

> independent replaceable systems.

Instead of clean abstractions, the architecture would slowly turn into a monolithic system where:

* every module depends on every other module
* changing one system breaks multiple others
* reasoning about the project becomes increasingly difficult

---

## Solution

The architecture switched to observation-based interaction:

```
World → Agent → Observation → Brain
```

instead of:

```
World → Brain
```

The brain now only receives limited observations rather than the full environment state.

This reduced coupling and made the system significantly cleaner.

---

# Logging System Overwriting Files

## Problem

After adding support for multiple episodes, logging appeared broken:
no matter how many episodes were executed, only one log file existed.

At first, the issue looked architectural:
* maybe the loop was incorrect
* maybe logging was attached to the wrong system
* maybe episodes were not isolated correctly

---

## Actual Cause

The issue was embarrassingly simple.
Log filenames used timestamps with second precision:

```
12:30:15.log
```

Episodes executed faster than one second.
As a result:
* multiple episodes generated the same filename
* logs overwrote each other

---

## Solution

Milliseconds were added to filenames.
Simple bug. Surprisingly annoying to diagnose.

---

#  Agent Escaping the Map

## Problem
After introducing Q-learning, the agent suddenly started moving outside map boundaries.
This had never happened with the earlier random policy system.

---

## Cause

Originally, movement safety worked through:

```
available_actions
```
The random policy selected only from valid actions.
However, after introducing Q-learning:
* actions came directly from the Q-table
* the Q-table contained ALL actions
* invalid moves were no longer filtered
The protection layer disappeared.

---

## Lesson
Changing decision architecture can silently invalidate earlier assumptions.
The movement system itself was not broken.
The action selection pathway changed.

---

# Argmax Collapse

## Problem

Without ε-greedy exploration, the agent repeatedly selected only actions:
* 0
* 1
even though all actions initially had equal value.

---

## Cause

All Q-values started as zeros:

```
[0,0,0,0,0,0,0,0]
```

`argmax()` simply returned the first maximum value.

This created deterministic bias toward early actions.

---

## Lesson

Pure greedy policies can create accidental deterministic behavior even in completely “neutral” systems.

Exploration is not optional.
Without it, the system may never meaningfully learn.

---

# The “Do Nothing” Exploit

## Problem

The agent discovered an unexpected strategy:

* stand still on positive cells
* avoid exploration
* minimize movement

This behavior was never explicitly programmed.

There was no “do nothing” action.

Yet the system still found a loophole.

---

## Why It Happened

The agent optimized reward exactly as instructed.

From the system’s perspective:

* movement has risk
* exploration has uncertainty
* staying on reward is safe

So the optimal short-term strategy became:

> stop moving.

---

## Lesson

Reinforcement learning systems optimize objectives literally, not semantically.

The agent does not understand:

* intended gameplay
* designer expectations
* “interesting behavior”

It only optimizes reward pressure.

This became one of the first truly “RL-like” moments in the project.

---

# Logging Improvements Destroyed Performance

## Problem

A more advanced logging system was planned:

* folder hierarchy
* automatic cleanup
* structured storage
* cleaner organization

The result:

* training slowed down by 3x–20x

---

## Lesson

Infrastructure systems can easily become hidden performance bottlenecks.

Sometimes:

> “good enough” architecture is better than overengineering.

---


# Discovering That TDD Actually Matters

## Problem

As the project grew, failures became increasingly difficult to diagnose.

A broken result could originate from:

* math
* reward shaping
* observation flow
* Q-table updates
* policy logic
* environment generation
* configuration mistakes

Without tests, debugging became chaotic.

---

## Solution

The project gradually shifted toward:

* isolated tests
* TDD for critical systems
* validation of interfaces and data flow

This created a much clearer distinction between:

* bad ideas
* broken implementations

which turned out to be one of the most valuable architectural improvements in Stage 1.
