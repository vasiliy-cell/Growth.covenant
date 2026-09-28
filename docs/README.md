# Growth.covenant - documentation

A population of DQN agents living in one continuous grid world. Every agent
has its own body (position, energy, age), its own DNA and its own mind
(network, replay buffer, exploration, curiosity). Agents eat, age, starve,
and reproduce; minds learn within a lifetime, and genes pass between
generations. Nothing outside the world ranks agents or picks survivors.

These pages describe **what the code does today**, rule by rule, with the
numbers from the current `config.yml`. Where a rule has a reason that
matters for the experiment, the reason is written next to it. The reasoning
behind each config key lives in [config.md](config.md).

If a page and the code disagree, the code is the experiment - fix the page.

## Reading order

| Page | What it answers |
|---|---|
| [overview.md](overview.md) | How the whole system works, in plain language, before any code |
| [architecture.md](architecture.md) | What the parts are, who owns what, and how one tick flows through them |
| [world.md](world.md) | The map, food and danger, refill, movement, collisions, what an agent sees |
| [life.md](life.md) | Energy, childhood, aging, starvation, reproduction - with worked numbers |
| [brain.md](brain.md) | Observation encoding, network, Double DQN, exploration, replay, reward shaping, curiosity |
| [genome.md](genome.md) | Genes, the three species (clons, non_linear, mendel), mutation, phenotype, frozen genes |
| [randomness.md](randomness.md) | The named rng streams, and why a run is reproducible |
| [checkpoints.md](checkpoints.md) | Saving and continuing a whole run; rolling and pinned checkpoints; the model archive |
| [logging.md](logging.md) | The log folder of a world, every table and column, and how to read it back |
| [running.md](running.md) | How to start, continue and watch runs; command line flags; scripts; tests |
| [panel.md](panel.md) | The local web panel: pages, what it reads, what it can change |
| [config.md](config.md) | Every key of `config.yml` and why it has its value |

## Glossary

- **tick / step** - one call of `GridWorldEnv.step()`: every living agent
  acts once, simultaneously. The run's global step counter is
  `env.current_step`.
- **episode / logging window** - `run.episode_length` steps. It resets
  nothing in the world. It only closes a row of summary tables and decays
  each mind's `epsilon` and curiosity `beta`.
- **run** - one process of `src/run.py`. It gets a new **run id**
  (`<YYYYmmdd>-<HHMMSS>-<6 hex>`).
- **world** - the map and population a run started. It keeps the id of the
  run that created it (**world id**) for as long as it is continued.
- **session** - one run's stretch of a world. A world continued three times
  from checkpoints has four sessions in its log.
- **agent id** - `<world id>-<index as 4 digits>`, unique across every run
  of the project. **index** - the agent's number inside its world; never
  reused.
- **genotype** - the DNA an agent passes on. **phenotype** - what that DNA
  was read into for this body (the numbers its mind is built from).
- **species** - the reproduction scheme of a run: `clons`, `non_linear` or
  `mendel`.
- **child / adult** - life periods (see [life.md](life.md)), not
  parent/offspring relations. A "newborn" is an agent at age 0.
- **env reward** - what the world pays for a cell (+5 food, -5 danger, 0
  empty). It is also the energy change. **shaped reward** - what a mind
  learns from: env reward + curiosity + food bonus.
