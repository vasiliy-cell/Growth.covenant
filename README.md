
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

##  Stage 1 — Foundation (Grid World + Q-Table)

At the first stage, the project implements a classic **grid-world environment**.

### World Generation

* The map is procedurally generated
* It consists of **64 cells**
* Each cell contains a number
* Numbers are mapped to objects:

  ```
  number → object
  ```

* **80% of the map is empty space**

* There is a **guarantee that all object types are spawned at least once**

This ensures both randomness and coverage of all possible interactions.

---

###  Agent Structure

Each agent consists of:

* **Body**
* **State**
* **List of available actions**

There is also a **global action space**, but:

> The agent cannot always perform all actions (e.g. movement depends on position)

---

###  Brain Architecture

The agent’s “brain” is divided into two main components:

#### 1. Q-Table (temporary component)

* Takes the **current state**
* Returns a score for each possible action:

  ```
  Q(state, action) → value
  ```

* Represents how “good” an action is
* Updated using a learning formula during training

---

#### 2. Policy (long-term component)

The policy decides **which action to take**, based on Q-values.

* Default behavior: choose the best action
* Sometimes uses **ε-greedy strategy**:

  * explore (random action)
  * exploit (best known action)

---

###  Learning Features

* **Curiosity-driven learning** (planned)
* Reward system (basic at this stage)
* Exploration vs exploitation balance

---

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



