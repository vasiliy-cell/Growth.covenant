## Growth.covenant
> An open-ended research project on which biological and social pressures
> are actually required before adaptive behaviour, evolution, and
> communication appear in artificial agents on their own.

**Status:** Stage 3 — artificial life / multi-agent evolution (in progress)

# OPUS MAGNUM COSMOGONICUM

+ _«Non in ordine mortuo, sed in chao se ipsum ordinante est vita: ex chao oritur anima, ex anima oritur verbum quod mundum regit.»_
+ _(Life lies not in a dead order, but in a chaos that orders itself: from chaos the soul is born, and from the soul is born the word that rules the world.)_

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

- **Artificial life, not genetic algorithms.** There is no external
  fitness function that ranks agents and picks survivors. Selection is
  endogenous: agents eat, run out of energy, die, choose mates, and reproduce
  inside the world.

  To be precise, there *is* an implicit fitness: energy. An agent's energy is
  what it collects from the environment minus what it constantly leaks, and an
  agent can reproduce only once it has gathered enough energy. So
  reproduction depends entirely on how well an agent turns the world into
  energy — but nobody scores it from outside; the world itself decides.
- **Emergence over authorship.** Behaviour should be learned, not scripted.
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

## AI usage

Full disclosure, since this matters for how the results should be read.

I use AI assistants (primarily Claude) in this project for exactly two things:

- **generating some chunks of code**
- **spelling and grammar checks** in text.

That is the whole list. Specifically, AI does **not**:

- design experiments or choose hypotheses;
- decide the architecture of the system or of the genome schemes;
- write papers, reports, or research conclusions;
- interpret results.

Every line of generated code or text is read and understood by me before it enters the
repository. Nothing goes in that I could not have written myself and cannot
explain. The research design, the reasoning behind it, and the conclusions are
mine.

This is verifiable, not just a claim: Claude appears as a separate contributor
in the commit history, so anyone can check line by line which parts were
written with AI assistance and which I wrote by hand.

---

## Roadmap

### Phase I — Foundations (Stages 1–2) — *done*

A grid world with a reward system and one agent that learns *stably*.
Stability is the entire point of this phase, since every later result is
measured against it.

#### day I // STAGE 1.0: MECHANICUS MORTUUS

- **Title:** _Ordo Mortuus: Machina Sine Anima et Code Tabularis_ _(The Dead Order: The Soulless Machine and the Codex of the Table)_

The basic infrastructure and the simplest possible learner.

- **World:** a grid map with food and danger objects, and a gym-style
  environment with a step loop and rewards.
- **Tooling:** logging, visualization, seeded runs.
- **Agent:** tabular Q-learning with an ε-greedy policy.

Limitation: a Q-table stores a value only for states it has actually
visited, so it cannot generalize.

#### day II // STAGE 2.0: PRIMUS CHAOS

- **Title:** _Scintilla Vitae: Metamorphosis Neuralis et Anima Emergens_ _(The Spark of Life: Neural Metamorphosis and the Emerging Soul)_

The Q-table is replaced by a neural network (DQN), which generalizes
across similar states.

DQN training is unstable out of the box, so most of this stage is
stabilization:

- experience replay and mini-batching
- target network and Double DQN
- gradient clipping
- ε-decay
- curiosity bonus with decay

Result: a single agent that learns stably. This is the baseline for all
later stages.

### Phase II — Research (Stages 3–5)

#### day III // STAGE 3.0: ARCA HAEREDUM

- **Title:** _Abdicatio Creatoris: Purgatorium Mortis, Electio Dignorum et Idealis Inimaginabilis_ _(The Abdication of the Creator: The Purgatory of Death, the Selection of the Worthy, and the Unimaginable Ideal)_

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

#### day IV // STAGE 4.0: DILUVIUM UNIVERSALE

- **Title:** _Temptatio Magna: Diluvium Aquarum Universi et Ignis Trialis_ _(The Great Trial: The Universal Flood of the Substrate and the Fire of Trials)_

How environmental change affects already biologically grounded agents:
unstable environments, richer environments, new action spaces.

#### day V // STAGE 5.0: IMPERIUM LOGOI

- **Title:** _Imperium Verbi: Ex Silentio in Culturam Summam et Verbum Sacrum_ _(The Empire of the Logos: From Silence to the Highest Culture and the Sacred Word)_

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

1. install requirements (requirements.txt)
2. run `./run.sh`

### Reproducibility

A specific seed can be passed at launch, and the seed used for a run is
recorded in that run's log files — so any run can be reproduced from its logs.

https://github.com/user-attachments/assets/dd9c73c2-4c0d-42ac-b3ff-7ee9cf9fd6ef



## research Results

*(nothing published yet — Stage 3 in progress)*


### **PROJECT ENDING**

> _«Ex ordine natus est chaos; in chao nata est vita. Vita iterum ordini se subiecit, sed chaos non perdidit; et vita exspectationem Creatoris transcendit. Et vita creavit verbum, et verbum erat summus apex existentiae.»_
>
> _(From order, chaos was born; in chaos, life was born. Life submitted to order once more, yet did not lose its chaos; and life surpassed the expectations of the Creator. And life created the word, and the word became the highest summit of existence.)_
