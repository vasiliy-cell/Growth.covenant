
# Architecture

The architecture of Stage 1 is built around one core idea:

> each system should have a clear responsibility and interact with other systems only through controlled interfaces.

The project is intentionally designed to minimize coupling between modules so that individual parts can later be replaced, extended, or rewritten without rebuilding the entire system.

This is especially important because the project is expected to evolve significantly over time:

* Q-tables will later become neural networks
* simple environments become large sandbox worlds
* reward systems become more biologically inspired
* single-agent systems become multi-agent ecosystems

Because of this, the architecture prioritizes:

* modularity
* abstraction
* replaceability
* scalability
* observability

rather than raw performance or implementation simplicity.

---

# Core Architecture

The system is split into several independent layers:

```
   Run / Pipeline
        ↓
    Environment
        ↓
      Agent
        ↓
Brain (Policy + Learning)
        ↓
      Action
        ↓
    Environment
```

Each part has a strictly defined responsibility.

Modules do not directly manipulate each other internally.
Instead, they communicate through clean inputs and outputs.

This separation allows the system to evolve without creating tightly coupled dependencies between components.

---

# Gym-like Architecture

Stage 1 uses a gym-style API inspired by OpenAI Gym environments.

The goal is not strict compatibility with Gymnasium itself, but adopting the same architectural philosophy:

* clear environment boundaries
* standardized interaction flow
* isolated learning systems
* predictable interfaces

The environment exposes:

* `reset()`
* `step(action)`
* `action_space`
* `observation_space`

This creates a stable interaction layer between the environment and any future learning system.

---

# Why a Gym-like Structure Was Chosen

Without abstraction, reinforcement learning systems quickly become difficult to scale.

A common architectural mistake is allowing:

* the brain to directly manipulate the world
* the world to depend on learning internals
* systems to freely access each other’s state

This creates:

* tight coupling
* hidden dependencies
* poor replaceability
* difficult debugging
* architectural collapse as complexity grows

The gym-like structure solves this by turning the environment into a controlled interface rather than a collection of directly connected systems.

---

# Responsibility Separation

One of the most important goals of the architecture is making sure each module has a single clear role.

---

## World

Responsible for:

* world generation
* object placement
* reward calculation
* episode lifecycle
* observations
* interaction rules

The environment defines:

> how the world behaves

The environment does **not**:

* learn
* optimize policies
* decide actions

---

## Agent

Responsible for:

* physical presence inside the environment
* position
* movement
* state tracking
* interaction execution

The agent acts as the bridge between the world and the brain.

The agent does **not**:

* learn policies
* optimize rewards
* understand environment generation

---

## Environment
this is abstraction level of gymstyle api 
Environment is agent + world 

---

## Brain

Responsible for:

* decision making
* policy execution
* value estimation
* learning updates

The brain receives observations and returns actions.

It does not directly access:

* the map
* environment internals
* object placement systems

This abstraction is extremely important for scalability.

---

# Observation-Based Architecture

One of the key architectural decisions in Stage 1 was switching from full-map access to observation-based input.

Initially, the idea was to pass the entire world map directly into the brain.
While simple at first, this approach creates several problems:

* excessive coupling
* poor scalability
* unnecessary information flow
* dependency between world structure and learning implementation

Instead, the brain only receives observations.

This creates a cleaner architecture:

```
World → Agent → Observation → Brain
```

rather than:

```
World → Brain
```

The result is:

* fewer direct dependencies
* cleaner abstractions
* easier replacement of systems
* more realistic information constraints

The brain only sees what the agent is allowed to observe.

---

# Abstraction Layers

The project intentionally introduces multiple abstraction layers even though the current system is relatively small.

At first this may appear unnecessary, but as complexity grows, abstraction becomes essential.

The architecture separates:

* environment logic
* world representation
* agent behavior
* learning systems
* reward systems
* experiment infrastructure

This prevents the project from turning into a single monolithic pipeline where every system depends on everything else.

---

# Replaceability

A major architectural goal of Stage 1 is replaceability.

The system is specifically designed so that:

* the brain can change without changing the environment
* reward systems can evolve independently
* policies can be replaced separately from value estimators
* visualization can be detached from training
* environment complexity can scale gradually

This is why the current Q-table implementation is treated as temporary.

The architecture is being built around future replacement.

---

# Internal vs External Rewards

The reward system is also architecturally separated.

There are two different reward categories:

## External rewards

Generated by the environment itself:

* positive objects
* danger objects
* environmental interactions

## Internal rewards

Generated by learning-related systems:

* curiosity
* exploration pressure
* future intrinsic motivation systems

The environment only provides environmental rewards.

Internal rewards are calculated separately to avoid mixing world logic with learning logic.

This separation keeps the architecture cleaner and allows intrinsic motivation systems to evolve independently later.

---

# Scalability Philosophy

Stage 1 is intentionally small, but the architecture is designed for future growth.

The current system is expected to later support:

* neural networks
* larger environments
* evolutionary algorithms
* memory systems
* communication between agents
* biologically inspired mechanisms

Because of this, the project prioritizes architectural stability early instead of continuously rebuilding the entire system later.

---

# Summary

The architecture of Stage 1 is not optimized for maximum performance or minimal code size.

It is optimized for:

* clarity
* modularity
* experimentation
* controlled evolution of the system

The main goal is creating an environment where increasingly complex forms of learning can later emerge without requiring the entire project to be rewritten every time a new learning system is introduced.
