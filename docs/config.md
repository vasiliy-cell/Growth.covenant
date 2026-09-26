# config.yml, explained

Every setting of a run lives in `config.yml` in the repo root. That file is
kept short on purpose - one line per key - and this document is where the
reasoning behind those keys is written down.

A run reads the live `config.yml` when it starts. A run continued from a
checkpoint takes its seed, species, world and population from the
checkpoint and reads this file for everything tunable (life, energy,
refill); the runner prints which sections changed since the checkpoint was
written.

One value can be overridden for a single run without editing the file:

```bash
python src/run.py --set life.childhood_steps=2000 --set world.size=32
```

---

## `run`

The world is never recreated: a run is one continuous process of
`episodes * episode_length` steps. An **episode is only a logging window**
(and the boundary where epsilon and curiosity decay). It resets nothing in
the world and never teleports an agent back to the start of the map. The
number of episodes is asked in the terminal before the run; only the window
length lives here.

- **`episode_length`** - steps per window. `total_steps = episodes * episode_length`.
- **`deterministic`** - asks torch to refuse non-deterministic kernels
  (`warn_only`, so nothing crashes mid-run over an op that has no
  deterministic version). On CPU this project is bit-exact anyway; the flag
  is what keeps that true if a GPU is ever used. Cross-machine
  bit-exactness is not promised by it - see the note on checkpoints in
  CLAUDE.md.

## `agents`

Every agent gets its OWN brain, replay buffer, epsilon and curiosity, so
these settings are per agent.

- **`count`** - only the default offered by the terminal prompt before the
  run: the population size is an experiment parameter, so it is chosen next
  to the run length.
- **`view_size`** - side of the square window an agent sees around itself.
  The window reaches `view_size // 2` cells to every side, so an even value
  is rounded up: 10 is really an 11x11 window. The network input is
  4 channels x the window, so this also sizes every mind.

  7 was plenty on the old 8x8 map - it showed almost all of it - and a
  keyhole on 64x64. 53 was tried and was worse: the one useful cell drowned
  among 2809 inputs.

### What the network actually sees

Not a setting, but the thing `view_size` decides. The window is one-hot:
each cell becomes four inputs (food, danger, another agent, off the map),
and an empty cell is all four at zero. The agent's position is NOT an
input. As raw 0..63 numbers x and y were the loudest inputs in a world
where position says nothing about where the food is - the networks valued
places instead of what they saw, and walked into walls.

## `world`

- **`size`** - side of the square map.
- **`empty_ratio`** - share of empty cells at the first (and only)
  generation. The rest is split evenly between the kinds of object, so 0.7
  means 15% food and 15% danger.
- **`refill.every`** - check the map every N steps.
- **`refill.threshold`** - food and danger are EACH topped back up to this
  share of the map, counted separately.

  Counted together (as they were once), the danger that agents learn to
  walk around kept the total up while the food was eaten: the refill never
  fired and the map drifted towards one food per two dangers, until
  touching anything was a losing bet.

## `logging`

One folder per WORLD, not per process: a run continued from a checkpoint
writes into the same folder and opens a new session in its `run.json`.

```
logs/<world_id>[_<label>]/
  run.json     how to repeat it: seed, config, commit, schema, species,
               gene set, library versions, sessions
  steps/       a row per agent per tick
  updates/     a row per gradient update
  episodes/    per agent and per population, one row per window
  events/      births (with parents and DNA) and whole lives
  world/       the map and the bodies on it, every N steps
  rng/         stream states, world often and agents rarely
```

Each table is a folder of finished parquet parts. Parquet writes its footer
at close, so one open file would be unreadable after a crash; a part is
closed and renamed into place, and `flush_every_steps` bounds what a
`kill -9` can cost.

**Nothing here is ever deleted automatically.** A log is deleted by a human
who has decided the experiment is over - `scripts/logs.py` archives one
with a note attached when the disk gets tight.

- **`dir`** - where the log folders go.
- **`flush_every_steps`** - close a part of every table this often.
- **`max_rows_per_part`** - ...or when a table has this many rows.
- **`world_snapshot_every`** - snapshot the map every N steps (0 = off).
- **`rng_world_every_episodes`** - map/movement/genome streams, per window.
- **`rng_agents_every_episodes`** - the agents' own streams: ~16 KB each,
  random bytes that do not compress, and the checkpoints carry them all
  anyway.
- **`archive_dir`** - where `scripts/logs.py` puts packed runs.
- **`panel_dir`** - the control panel's own files: the live frame of each
  running world, the watch requests that slow a run down while it is being
  looked at, the consoles of runs it started. Never inside `dir`: they are
  views of a run, not a record of it.

## `checkpoints`

Two different things live here and they answer different questions.

`models_dir` holds the ARCHIVE: one file per agent, written when that agent
dies and at the end of the run, under `models/<run_id>/<agent_id>.pth`. It
says what a mind had learned. It is never read back.

`dir` holds the CHECKPOINTS: the whole run in one file - world, bodies,
DNA, every mind, every rng stream - written every `every_steps` ticks so a
crash costs minutes instead of a night. It has two folders, and which one a
file sits in is all there is to being pinned:

```
<dir>/rolling/   every save lands here; the newest checkpoint of each of
                 the `keep` most recent RUNS survives, nothing else
<dir>/pinned/    nothing is ever deleted from here
```

So pinning is moving a file - from the terminal, from a file manager, from
anywhere (`scripts/checkpoints.py pin 3` is only shorthand). The two
folders never compete: a prune looks at `rolling/` alone, so pinning four
checkpoints still leaves `keep` runs that can be continued. Counting runs
and not files matters: a long run saves every `every_steps`, and counted by
file those saves would push every other run's checkpoint out.

- **`models_dir`**, **`dir`** - the two folders above.
- **`every_steps`** - write a checkpoint every N steps (0 = off).
- **`replay_every`** - every Nth checkpoint also carries the replay
  buffers. They are most of the weight of a file, so the cheap ones are for
  crashes and the heavy ones for picking a run back up days later. A mind
  resumed without its memories is not broken - it refills the buffer from
  the world.
- **`keep`** - how many runs' newest checkpoints survive a prune; pinned
  ones are forever.

## `reward_shaping`

What a mind learns from, on top of what the world pays.

- **`food_bonus`** - added to the intrinsic reward on every step the world
  paid something positive. The world still pays +5 for food and -5 for
  danger, and energy still follows the world; only the reward the network
  learns from is louder, so food is learned as +10 against danger's -5.

  With food and danger both worth 5, touching a cell was a zero-sum bet and
  avoiding everything was the safe optimum.

## `energy`

What the world charges for being alive and what it takes to make a child.
Note that the reward the world pays goes straight into energy: one food
cell is +5 reward AND +5 energy.

- **`energy_leak`** - the BASE cost of being alive, paid by every agent on
  every tick. Aging adds to it (see `life.aging`), so this is what a
  newborn pays and nobody ever pays less.
- **`start_energy`** - what a body is born with. A newborn gets
  `reproduction_cost` from its parents instead.
- **`reproduction_threshold`** - an agent at or above this energy makes a
  child (asexually; the sexual species also matches partners by distance).
- **`reproduction_cost`** - what the parents pay for it, and what the child
  is born with. One parent pays it all; two parents pay half each.

  Keep it BELOW `reproduction_threshold`. At or above it, every newborn is
  born already able to reproduce, and the population explodes.

Reproduction is gated by energy alone - **not** by age. A newborn that has
the energy can have a child on its first tick; childhood only protects it
from death.

## `life`

A life has two periods, and the first one is free.

**Childhood** - the first `childhood_steps` ticks after birth. The agent
ages and leaks energy like everybody else, but nothing can kill it: every
newborn gets the same amount of time to learn where the food is before the
world starts charging for mistakes. Its energy is not floored, so a child
that eats less than it leaks goes on into debt and can die the moment it
grows up.

**Adulthood** - everything after that. The agent is mortal, and starvation
is the only way out: once its energy falls to `death_energy` it is removed
from the run.

There is no hard age limit on purpose. The personal leak grows by
`aging.amount` every `aging.every` ticks of a life and never stops growing,
so old age is not a number to compare against - it is a bill that keeps
rising until no amount of foraging can pay it.

- **`childhood_steps`** - ticks of guaranteed immortality after birth.
- **`death_energy`** - an adult at or below this energy dies.
- **`aging.every`** / **`aging.amount`** - every N ticks of a life, the
  personal leak grows by this much. The leak at age A is
  `energy_leak + (A // every) * amount`.

## `genome`

Every value in the project that changes HOW an agent learns, written as a
gene: a distribution to draw a newborn from instead of a single number
shared by everybody. `mean` is the hand-tuned value, so a population born
with `scale: 0` everywhere is a run where every agent is identical.

This section is the SOURCE OF TRUTH for the brain: every newborn's brain is
built from a genome sampled here
(`make_first_genome` -> `make_phenotype` -> `BrainManager` ->
`DQNTrainer`/`MLP`/`Policy`/`Curiosity`).

- **`type`** - which reproduction species this run uses: `clons` (asexual),
  `non_linear` (BLX-a blend of two parents) or `mendel` (dominant and
  recessive alleles). Asked in the terminal too; this is the default.

### The shape of a gene

The same for all of them, so the sampler never has to special-case
anything:

- **`mean`** - center of the draw.
- **`scale`** - stddev of the draw; 0 freezes the gene at `mean`.
- **`type`** - `float` or `int`, how the drawn number is rounded.
- **`step`** - round to a multiple of this.

### Mutation

A child's genome is its parent's, redrawn: every gene gets `N(0, sigma)`
added to it, and with probability `sigma` it is also multiplied by
`U(0.2, 5.0)`. Because that noise is ABSOLUTE, `sigma` has to stay small:
at 0.5 a learning rate of 0.001 became 0.3.

A few genes are checked after every draw and every mutation, because the
values outside those ranges do not merely make a worse agent, they break
learning outright:

- `gamma` is kept inside (0, 1), 0.001 or 0.999 at the edges,
- `learning_rate` and `max_norm` are made positive - a negative `max_norm`
  makes `clip_grad_norm_` flip every gradient, and the network learns
  backwards,
- `epsilon_decay` and `curiosity_decay` above 1 become 0.999 - a decay
  above 1 makes epsilon or curiosity GROW instead of fading,
- `sigma` below 0 becomes 0.01.

### The genes

**Reproduction**

- `alpha` - how far outside the parents' range a `non_linear` child may be
  drawn (BLX-a).
- `sigma` - the width of mutation, and the chance of a huge one. See above.

**Optimizer**

- `learning_rate` - Adam's step size.
- `max_norm` - gradient clipping. It is the tightest clip in the project,
  so it decides the effective learning rate far more than `learning_rate`
  does; it belongs in the genome next to it.

**DQN targets** - how far ahead this mind looks and how stale the target it
chases is.

- `gamma` - discount factor. The world has no terminal state, so the value
  of a state is roughly `reward per step / (1 - gamma)`: at 0.999 that is a
  thousand steps of reward, and Q takes very long to converge.
- `target_update_freq` - updates between two copies of the policy net into
  the target net. Large values make Q climb in visible staircases, one step
  per sync, and the loss grow with it.

**Network shape** - the capacity of the mind itself.

- `hidden_size`, `hidden_layers` - the MLP between the window and the eight
  action values.

**Memory** - one agent stores exactly one transition per tick, so these are
ticks of personal history.

- `buffer_size` - how far back this mind can remember.
- `batch_size` - how much of it it revisits per update.
- `min_buffer_size` - how long it waits before learning at all.

**Exploration** - the schedule follows the age of the individual, not the
age of the run, so an agent born late still starts out exploring.

- `epsilon` - start value.
- `epsilon_decay` - applied per logging window.
- `epsilon_min` - the floor. Too low a floor and an agent that falls into a
  two-cell shuttle at a wall has nothing left to break out with.

**Curiosity** - the intrinsic half of the reward: how loudly novelty pays
and how fast that voice fades. The visit counts are cleared at every
logging window, and the key is the map around the agent WITHOUT the other
bodies.

- `curiosity_beta` - the strength. 4.0 against a food cell worth +5 means a
  newborn is driven mostly by curiosity.
- `curiosity_decay` - applied per logging window.
