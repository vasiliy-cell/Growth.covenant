# Growth.covenant

> An open-ended research project on which biological and social pressures
> are actually required before adaptive behaviour, evolution, and
> communication appear in artificial agents on their own.

**Status:** Stage 3 — artificial life / multi-agent evolution (in progress)

---

## The question

The project revolves around one question, approached from many angles:

**Which properties of evolution,language and environment produce more capable agents?**

Growth.covenant is not built around a single powerful model. The system grows
in stages — tabular policy → neural policy → population → environment →
language — and each stage after the second is an experiment, not just an
engineering milestone.

---

## Position

A few commitments that shape every design decision here:

- **Artificial life, not genetic algorithms.** No external fitness function
  ranks agents and picks survivors. Selection is endogenous: agents eat, run
  out of energy, die, choose mates, and reproduce inside the world. Fitness
  metrics exist *only* as instruments of observation — never as a selection
  mechanism.
- **Emergence over authorship.** Behaviour should be learned, not scripted.
  There is no `if energy > threshold: reproduce` rule; mate choice and
  reproduction have to come out of the agent's own policy.
- **Biology as inspiration, not as a specification.** Only the mechanisms that
  buy something are reproduced: mutation, recombination, dominance/recessivity,
  genetic diversity, speciation. Faithful biochemistry is deliberately out of
  scope.
- **The environment is the independent variable.** Where possible, the
  environment is frozen and one factor at a time is varied against a baseline.

---

## Method
Each research stage follows the same shape:

1. one abstract question
2. a set of smaller, testable hypotheses
3. shared constraints (frozen environment, fixed seeds, fixed budget)
4. a baseline
5. one experiment per hypothesis — theoretical rationale, then run
6. hypotheses compared against each other and against the baseline
7. conclusion

---

## Roadmap

### Phase I — Foundations (Stages 1–2) — *done*

A grid world with a reward system and one agent that learns *stably*.
Stability is the entire point of this phase, since every later result is
measured against it. Implemented: experience replay, mini-batching, target
network, Double DQN, gradient clipping, ε-decay, curiosity with decay.

### Phase II — Research (Stages 3–5)

#### Stage 3 — Alife: multi-agent evolution

Many agents in one world. Genomes are inherited; weights are not — a genome
carries the *recipe* (layer count, neuron count, learning rate, γ, buffer and
batch size, mutation magnitude, and so on), and every agent still learns its own weights
within its lifetime.

Directions under investigation:

- **What is inherited** — genome size (minimal / medium / large).
- **How it is inherited** — competing genome-encoding schemes, compared
  head to head: a Mendelian table with explicit dominant/recessive flags
  (baseline), a vector scheme merging two parental vectors through a
  non-linear transform, and a probabilistic ancestral pool where recent genes
  are more likely to resurface.
- **How selection happens** — sexual selection, mate-choice criteria, the cost
  of reproduction.
- **Social pressure** — which available actions (sharing, killing, displays of
  strength) change how the population develops. Scheduled last.

#### Stage 4 — Sandbox environment

How environmental change affects already biologically grounded agents:
unstable environments, richer environments, new action spaces.

#### Stage 5 — Language

The largest and least certain stage.

1. Can a language appear without being taught — given only a channel to pass
   information through?
   - which properties of the environment or of the agents make it appear?
   - how do you establish that a language has appeared at all?
   - what does it look like — structure, syntax, compositionality?
2. Once it exists: how does having a language change behaviour?

### Beyond

Deliberately unspecified. Most likely: closing questions left open by
Stages 3–5, or pushing evolution further.

---
## Running it

1. instal requirements (requirements.txt)
2. run `./run.sh`

<video src="https://github.com/vasiliy-cell/Growth.covenant/raw/main/docs/Attachments/demo.mp4" controls width="640"></video>



## Results

*(nothing published yet — Stage 3 in progress)*