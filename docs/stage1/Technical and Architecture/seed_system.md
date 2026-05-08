# Deterministic Experiment Pipeline

The architecture also includes deterministic experiment control through seeds.

Randomness flows through controlled RNG pipelines rather than uncontrolled global randomness.

This enables:

* reproducible experiments
* deterministic debugging
* controlled comparisons
* stable testing

The randomness pipeline follows this structure:

```
   Run
    ↓
Global Seed
    ↓
Environment RNG
    ↓
  World
    ↓
Map Generation
```

This prevents randomness from becoming scattered across unrelated systems.

---

