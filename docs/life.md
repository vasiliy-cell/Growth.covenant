# Life: energy, childhood, aging, death, birth

Code: `src/Agent/life.py` (the rules), `src/Agent/agent.py` (one body's
numbers), `src/environment/env.py` (`step`, `_reap`, `_reproduce`,
`_birth`), `src/Behavior/Choosing_partner.py`.

`Life` is built once from the `life` and `energy` sections of
`config.yml` and shared by every body. An agent carries only its own
`energy`, `age` and `adult_at`, and asks `Life` what they mean.

## Energy

- The world's reward **is** the energy change: food +5, danger -5, empty 0.
- Every tick, each agent pays a **leak** (the cost of being alive).
- Energy is capped at `energy.max_energy` (300) when food is added - what
  would go above the ceiling is lost. The cap is applied **before** the
  leak, so right after a tick an agent holds at most `300 - leak`.
- Founders (the first population) are born with `energy.start_energy`
  (50). A newborn gets `energy.reproduction_cost` (100) instead.

The reward a mind learns from is not the same as energy: the food bonus
and curiosity are added to it (see [brain.md](brain.md)), but energy only
ever follows the world.

## Two periods of a life

### Childhood

Childhood lasts from birth until **whichever comes first**:

- `life.max_childhood_steps` ticks (2500), or
- the tick the agent first becomes a parent (`Agent.grow_up()` sets
  `adult_at` to its age at that moment).

A child:

- pays the **base leak only** (`energy.energy_leak`, 0.5) - age costs a
  child nothing,
- pays only **down to zero**: its energy never goes below 0 after a tick
  (`max(energy - leak, 0)`), so a child cannot go into debt,
- **cannot die**, whatever its energy.

Danger still takes energy from a child, but the same floor applies at the
end of the tick.

Why the floor: a leak with no floor made a hungry child build up debt all
childhood and starve on the first adult tick. No leak at all made
childhood a savings account.

### Adulthood

Everything after childhood. An adult:

- pays the full leak, and may go below zero,
- dies at the end of the leak step if its energy is **at or below**
  `life.death_energy` (-20).

Starvation is the only cause of death in this world. Danger, aging and
losing a cell to a neighbour all end up as energy the agent could not
replace.

## Aging - how fast the leak grows

For an adult:

```
leak = energy_leak + floor(adult_age / aging.every) * aging.amount
     = 0.5         + floor(adult_age / 200)        * 0.05

adult_age = age - adulthood
adulthood = min(adult_at, max_childhood_steps)   (adult_at = None -> 2500)
```

So the count starts at the **end of childhood**, not at birth. It is a
staircase: +0.05 every 200 adult ticks, i.e. +0.25 per 1000 ticks, and it
never stops. There is no maximum age; the bill simply outgrows what any
agent can forage.

| adult age (ticks) | leak / tick | food cells needed to break even |
|---|---|---|
| 0 - 199 | 0.50 | 1 per 10 ticks |
| 1000 | 0.75 | 1 per ~6.7 ticks |
| 2000 | 1.00 | 1 per 5 ticks |
| 4000 | 1.50 | 1 per ~3.3 ticks |
| 10000 | 3.00 | 1 per ~1.7 ticks |
| 18000 | 5.00 | 1 every tick |

- The leak doubles after 2000 adult ticks.
- Total leak over the first A adult ticks is about `0.5*A + A^2/8000`
  (≈1500 energy for A = 2000).
- Past ~18000 adult ticks, eating food on every single tick no longer
  pays the leak. With food at 10% of cells, that point is never reached in
  practice - an agent dies of age long before.
- The reserve between a full stomach and death is `300 - (-20) = 320`
  energy: about 640 ticks without food at leak 0.5, 320 at leak 1.0, about
  107 at leak 3.0.

`aging.every: 0` switches aging off (the leak stays at the base).

### Example: a founder that never eats

Born with 50 energy. It pays 0.5 per tick and reaches 0 at tick 100, then
stays at 0 (childhood floor) until its childhood ends at age 2500. As an
adult it goes 0 → -0.5 → -1.0 ... and dies on the tick its energy reaches
-20, 40 ticks later - a lifespan of about 2540 ticks.

## Order inside a tick

In `GridWorldEnv.step`:

1. move (all agents at once),
2. for each agent: **eat** (reward added, capped), clear the cell,
   **leak** (paid at the age the agent had during this tick),
3. **death** - adults at or below `death_energy` are removed,
4. **aging** - every survivor's `age += 1`,
5. **birth** - reproduction on what is left alive,
6. refill, observe.

Consequences:

- death before birth: a starving agent does not reproduce on its last
  tick,
- aging after death: an agent is immune for exactly
  `max_childhood_steps` whole ticks (ages 0 ... 2499),
- a parent's `adult_at` is its age after this tick's aging; from the next
  tick it pays the adult leak, starting at the base.

## Reproduction

Gated by **energy and nothing else** - not by age, not by distance, not by
a choice of the agent's mind. It is checked every tick, after deaths and
aging.

### Asexual (`clons`)

Every agent with `energy >= energy.reproduction_threshold` (100) makes one
child this tick:

- the child's genome is the parent's, mutated (see
  [genome.md](genome.md)),
- the parent pays `reproduction_cost` (100) in full,
- the child is born with 100.

One child per parent per tick. A parent with a full stomach (≈300) can
breed on up to three ticks in a row.

### Sexual (`non_linear`, `mendel`)

`choose_partners`: everybody with `energy >= reproduction_threshold` is
listed in population order (spawn order), and the list is cut into pairs:
1st with 2nd, 3rd with 4th, and so on. The first of a pair is the
"mother", the second the "father". Distance does not matter - an agent
across the map is as good a partner as a neighbour. An odd one out waits
for the next tick.

Each pair makes one child; each parent pays `reproduction_cost / 2` (50);
the child is born with 100.

Distance was removed on purpose: pairing by proximity rewarded crowds in
corners, where partners are always within reach.

### What a birth does

`GridWorldEnv._birth`:

- spawns a body on a random free cell anywhere on the map (the
  `population` stream),
- gives it the next index, age 0, `birth_step` = current step, and the
  parents' ids,
- stores its genotype in the gene pool,
- sets its energy to `reproduction_cost`,
- for every parent: `offspring += 1` and `grow_up()` - **breeding ends
  childhood on the spot**, however young the parent is.

The newborn gets its mind and acts from the next tick on.

Note on the current numbers: `reproduction_threshold` and
`reproduction_cost` are both 100, so a newborn starts exactly at the
threshold. If it eats food on its first tick (100 + 5 - 0.5 = 104.5) it
reproduces on that tick (for a sexual species, if the pairing gives it a
partner) and becomes an adult at age 1, with 4.5 energy left (clons) or
54.5 (sexual). [config.md](config.md#energy) advises keeping the cost below
the threshold.

## Identity and lineage

- An agent id is `<world id>-<index:04d>`, e.g.
  `20260920-183709-229d1f-0012`. The world id is the run id of the process
  that created the world, `<YYYYmmdd>-<HHMMSS>-<6 random hex>`.
- The index counter only goes up and is restored from checkpoints, so an
  index is never reused - it also names the agent's rng streams.
- Every birth records its parents (empty list for founders) and is
  logged, founders included, so the family tree has roots.
- A death record carries the whole life: birth and death step, lifespan
  (the age at death), cumulative env reward, number of children, final
  energy and the genotype. The genotype stays in the gene pool after
  death.

## Parameters in play

| key | now | effect |
|---|---|---|
| `energy.energy_leak` | 0.5 | base leak per tick |
| `energy.start_energy` | 50 | founders' starting energy |
| `energy.max_energy` | 300 | stomach ceiling (null = none) |
| `energy.reproduction_threshold` | 100 | energy needed to reproduce |
| `energy.reproduction_cost` | 100 | what parents pay, what the child gets |
| `life.max_childhood_steps` | 2500 | longest childhood |
| `life.death_energy` | -20 | an adult at or below this dies |
| `life.aging.every` | 200 | adult ticks per aging step |
| `life.aging.amount` | 0.05 | leak added per aging step |

All of these are read from the live `config.yml`, also when a world is
continued from a checkpoint.
