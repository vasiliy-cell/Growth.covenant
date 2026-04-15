
(current CURRENT STAGE IS 1)

---

# Growth.covenant

**Growth.covenant** is an experimental research project exploring the emergence of intelligence, behavior, and communication in artificial agents.

The core idea is simple but ambitious:
build a system where intelligence is not hardcoded, but **grows step by step** through interaction with the environment, evolution, and eventually language.

This project is not just about reinforcement learning.
It is an attempt to simulate a **path from simple agents to complex adaptive systems**.

---

## Concept

Growth.covenant is my personal experiment in building intelligence from the ground up.

Instead of starting with a powerful neural network, the system evolves through stages:

* from simple rule-based behavior
* to reinforcement learning
* to neural networks
* to evolution
* to communication
* and eventually toward biologically inspired systems

---

### Stage 1 — Foundation (Environment + Learning Core)

The goal of this stage is to build a reliable environment where learning actually works.

Before introducing a real AI, I need to be sure that:

- the world makes sense
- rewards are meaningful
- and the system naturally pushes the agent to learn

Otherwise, it becomes impossible to tell whether problems come from the model or the environment.

At this stage, I build:

- a simple grid-world with basic interactions (reward, danger, empty space)
- a reward and logging system
- a minimal agent (movement, state, observations)
- a basic learning core: Q-table + policy

This is not the final intelligence, but a **temporary learning mechanism** used to validate the system.

If learning doesn’t emerge here, the issue is in the environment, not the “brain”.

##  Roadmap

### Step 1 — Base System

* Q-Table implementation
* Grid-world environment
* Reward system
* Curiosity-driven learning

---

### Step 2 — Brain Replacement

Once the system is stable:

* Replace Q-Table with a neural network
* Keep everything else unchanged:

  * same world
  * same rewards
  * same environment

> Only the “brain” changes

---

### Step 3 — Genetic Algorithms

Introduce evolution:

* Population: **10–30 agents**
* Mutation
* Selection (survival of the fittest)
* Optional crossover

Goal: evolve better strategies over generations.

---

### Step 4 — Sandbox Environment

Gradually increase complexity:

* Increase map size
* Allow agents to adapt
* Add new object types:

  * food
  * dangers
  * bonuses
  * upgrades

Also introduce:

* **Memory system**

Transition:

```
Grid World → Sandbox
```

---

### Next Steps — Flexible Direction

In the following stages, the project may expand in multiple directions depending on experimental results, constraints, and emerging ideas.

This includes the introduction of communication between agents, where interaction may evolve from simple signals into structured language. The system may incorporate neural architectures such as Transformer-based models, allowing agents to develop their own communication protocols.

Further development may move toward biologically inspired systems, including genome-based representations, evolutionary pressure, reproduction mechanisms, and more advanced selection dynamics.

There is also interest in exploring more realistic forms of computation, such as lightweight spiking neural networks, aiming to approximate biologically plausible behavior without unnecessary complexity.

The exact order, depth, and priority of these directions are intentionally left undefined and may change over time as the project evolves.

---



