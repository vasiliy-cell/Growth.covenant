# How it works

A plain-language picture of the whole system, before the details of each
part. Every statement here is a description of what the code does; the
numbers are the current `config.yml` values.

## The world

One square map, 64 x 64 cells. About 10% of the cells hold food (+5
energy), about 10% hold danger (-5 energy), the rest are empty. A cell an
agent steps on is eaten and becomes empty. Every 5 steps the map tops each
kind back up to its share, on random empty cells. The map is created once
and never reset, so the world is one continuous run with no episodes and
no end state.

## A body

An agent is a body on one cell. Every tick it moves one cell in one of 8
directions (all agents at the same time, one body per cell; when two want
the same free cell, one of them gets it at random). It sees an 11 x 11
window around itself: food, danger, other agents, the edge of the map. It
does not see its own coordinates, energy or age.

A body has **energy**. Food adds to it, danger takes from it, and every
tick costs a **leak**. The stomach holds at most 300.

## A life

- **Childhood** - from birth, up to 2500 ticks. A child pays a flat leak of
  0.5 per tick, cannot go below 0 energy and cannot die.
- **Adulthood** - begins when childhood runs out, or earlier, the moment
  the agent has its first child. An adult pays 0.5 per tick plus 0.05 for
  every 200 ticks of adult life, without limit, and dies once its energy
  falls to -20.

Death by starvation is the only way an agent leaves the world. Because the
adult leak keeps rising, every adult eventually starves.

## Reproduction

Checked every tick, on energy alone:

- `clons`: every agent with at least 100 energy makes one child and pays
  100,
- `non_linear`, `mendel`: all agents with at least 100 energy are paired
  two by two in population order; each pair makes one child and each
  parent pays 50.

The child is born with 100 energy on a random free cell of the map, as a
child (age 0). The mind does not decide to reproduce: it happens whenever
the energy condition holds.

## A mind

Every agent has its own, private mind - a small neural network trained
with Double DQN on the agent's own experience:

- it sees the 11 x 11 window (one-hot, 484 numbers) and outputs a value for
  each of the 8 moves,
- it acts epsilon-greedy: a random move with probability epsilon,
  otherwise the move with the highest value,
- after each tick it stores the transition in its own replay buffer and,
  once the buffer holds enough transitions, takes one gradient step,
- it learns from the world's reward plus two additions: a food bonus (+5
  on food, so food counts +10 to the mind) and curiosity (a bonus for
  states this agent has seen rarely, `beta / sqrt(visits)`),
- every 20 ticks (one logging window) its epsilon and its curiosity
  strength shrink by a factor.

A newborn's mind starts with random weights. **Weights are never
inherited.**

## Genes

What is inherited is the **recipe of the mind**: 16 numbers (genes) that
set how it learns - learning rate, gradient clip, discount, target-network
period, network width and depth, replay size, batch size, warm-up,
epsilon schedule, curiosity schedule - plus two genes of reproduction
itself (`sigma`, the per-gene mutation probability, and `alpha`, used by
`non_linear`).

- Founders draw each gene from a normal distribution around its config
  mean.
- A child gets its genes from its parent(s) according to the species
  (copy, blend, or two alleles with dominance), then each gene mutates
  with probability `sigma` by a random factor between 0.5 and 2.
- Genes left out of `genome.evolve` are frozen at their mean for everybody.

The genes become the body's **phenotype** once, at birth, and the mind is
built from it.

## How it fits together

```
genes ──read once──▶ phenotype ──builds──▶ mind
                                            │ chooses moves
                                            ▼
             world ◀──── moves ──── body (position, energy, age)
               │                        ▲
               └── food / danger ───────┘
                                        │
                energy ≥ 100 ──▶ child (new genes, new random weights)
                energy ≤ -20 (adult) ──▶ removed
```

Nothing in the code scores agents or picks who survives. An agent's genes
reach the next generation only if its body gathers enough energy to
reproduce before it starves; everything the genes do, they do through the
mind's behaviour in the world.

## One agent's timeline with the current numbers

| ticks of life | what is going on |
|---|---|
| 0 | born with 50 (founder) or 100 (child) energy, random weights |
| 0 - ~500 | replay buffer filling (`min_buffer_size` ≈ 500): moves come from the untrained network and epsilon; no learning yet |
| ~500 on | one gradient step per tick |
| 2500 | childhood ends (unless the agent has bred before); with the mean genes, epsilon is still ≈ 0.37 and curiosity strength ≈ 0.53 of its start |
| ~10500 | with the mean genes, epsilon reaches its floor (≈ 0.05) |
| adult + 2000 | leak has doubled to 1.0 per tick |
| adult + ~18000 | leak reaches 5 per tick - more than one food cell per tick can pay |

## What is recorded

Every tick of every agent, every gradient update, a summary per logging
window (per agent and for the population), every birth with its genes,
every death with the whole life, snapshots of the map, and the state of
every random stream. A whole run can be saved to a checkpoint and
continued exactly where it stopped. See [logging.md](logging.md) and
[checkpoints.md](checkpoints.md).
