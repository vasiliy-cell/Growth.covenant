# Logging

Code: `src/persistence/run_log.py` (writer), `log_schema.py` (columns),
`log_reader.py` (reader), `scripts/logs.py`.

## One folder per world

```
logs/[<series>/]<world_id>[_<label>]/
  run.json                 header: how to repeat it, one entry per session
  steps/                   a row per agent per tick
  updates/                 a row per gradient update
  episodes/agents/         a row per agent per logging window
  episodes/population/     a row per logging window
  events/births/           a row per birth (founders included)
  events/deaths/           a row per death
  world/grid/              the map every `world_snapshot_every` steps
  world/agents/            positions at those same steps
  rng/world.jsonl          world stream states
  rng/agents.jsonl         agent stream states
```

- The folder belongs to the **world**, not the process. A continued world
  is found by its id and gets a new **session** in the same folder.
- `label` is the optional experiment name asked at start (made
  folder-safe). `series` (`--series`) nests the folder one level down.
- **Nothing is ever deleted automatically.**

### Tables are folders of parquet parts

Parquet writes its footer only on close, so one open file would be
unreadable after a crash. Each table is a folder of finished parts
`part-s<session>-<n>.parquet` (zstd). A part is closed every
`logging.flush_every_steps` steps (1000) or when a table reaches
`logging.max_rows_per_part` rows (50000), written to a temp name and
renamed into place. A `kill -9` costs at most the rows still in memory.

### Types

Floats are float32; sums (window rewards), wall clock and hashes are
float64 or strings. Every row carries `session`: two rows may claim the
same step if a world was continued from a checkpoint older than rows
already on disk - `session` tells them apart.

## `run.json`

Written at start and rewritten (atomically) on every flush:

- `schema_version`, `world_id`, `label`, `series`, `created_at`,
  `episode_length`, `species`, `genes`, `config` (first session's),
  `commit`, `versions` (python, numpy, pyarrow, torch),
- `sessions`: one entry per run of this world - `session`, `run_id`,
  `seed`, `commit`, `started_at`, `finished_at`, `resumed_from`
  (checkpoint file name), that session's `config`, `from_step`,
  `to_step`, `from_episode`, `to_episode`.

## The tables

### `steps` - one row per agent per tick

| column | meaning |
|---|---|
| `step`, `session`, `wall_clock` | when |
| `agent_id` | who |
| `x`, `y` | position **before** this tick's move (where it acted from) |
| `action` | move id 0-7 |
| `env_reward` | what the world paid (+5 / -5 / 0) |
| `intrinsic_reward` | curiosity + food bonus |
| `shaped_reward` | env + intrinsic, what went into the buffer |
| `energy` | energy at the end of the tick (after eating, leak and any reproduction cost) |
| `age` | age after the tick |

For an agent that died on this tick: `intrinsic_reward = 0`,
`shaped_reward = env_reward`, `energy` is its final energy and `age` its
lifespan.

### `updates` - one row per gradient update

`step`, `session`, `wall_clock`, `agent_id`, `training_step` (this
mind's update counter), `loss`, `grad_norm` (before clipping),
`td_error` (mean target - Q), `target_q`, `q_prediction` (batch means),
`curiosity_beta`, `epsilon`, `buffer_size`. A mind still warming up its
buffer has no rows here.

### `episodes/agents` - one row per agent per window

`episode`, `session`, `step_start`, `step_end`, `agent_id`, `steps`
(ticks it was logged in this window), `env_reward`, `intrinsic_reward`,
`shaped_reward` (window sums, float64), `epsilon`, `curiosity_beta`,
`energy`, `age`. Epsilon/beta/energy/age are taken at the end of the
window; for an agent that died inside the window, energy and age are those
of its last logged step and epsilon/beta are empty.

### `episodes/population` - one row per window

| column | meaning |
|---|---|
| `episode`, `session`, `step_start`, `step_end` | the window |
| `wall_clock`, `duration` | when it closed, how long it took |
| `agents` | alive at the end of the window |
| `births`, `deaths` | during the window |
| `steps` | agent-steps logged |
| `env_reward`, `intrinsic_reward`, `shaped_reward` | population sums |
| `updates`, `mean_loss`, `mean_td_error` | gradient updates in the window; `mean_td_error` is the mean of absolute per-update values |
| `mean_epsilon`, `mean_curiosity_beta` | over living minds |
| `non_empty_ratio` | share of the map holding food or danger |
| `fingerprint` | rolling hash of every step logged so far |

The runner prints this row to the terminal at every window.

### `events/births`

`step`, `session`, `wall_clock`, `agent_id`, `index`, `parents` (list;
empty for founders), `energy` (at birth), `genotype_json`, and one
`phen_<gene>` float32 column per gene. Founders are logged at step 0.

### `events/deaths`

`step`, `session`, `wall_clock`, `agent_id`, `index`, `parents`,
`birth_step`, `death_step`, `lifespan`, `cumulative_reward` (env reward
over the whole life), `num_offspring`, `cause_of_death` (always
`starvation`), `energy`, `genotype_json`.

### `world/grid`, `world/agents`

Every `logging.world_snapshot_every` steps (100; 0 = off): the map as a
flat int8 list with its `size` (objects only), and one row per agent with
its `x`, `y`. Bodies are kept apart so they do not hide the cell they
stand on.

### `rng/*.jsonl`

At the end of every window, before the window counter moves: the world
streams every `rng_world_every_episodes` windows (1), the agents' streams
every `rng_agents_every_episodes` windows (100). Each line: session,
episode, step, seed, streams.

## The live frame

Not part of the record: `<panel_dir>/live/<world_id>.json`, rewritten
every `logging.live_every_steps` steps (20 by default; the key is not in
`config.yml`), or every step while somebody watches, but never more than
60 times a second. It holds the step, episode, population size, the
window's reward so far, mean epsilon, steps per second, the grid (base64
int8) and positions, plus pid and run info. At the end of a run it is
marked `"finished": true`.

## Reading a log

```python
from src.persistence.log_reader import RunLogReader

worlds = RunLogReader.find("logs")         # every world, newest first
log = worlds[0]
log.header                                  # run.json
log.sessions
pop = log.episode_population()              # pyarrow.Table
df = pop.to_pandas()                        # if pandas is installed
log.steps(); log.updates(); log.episode_agents()
log.births(); log.deaths()
log.world_grid(); log.world_agents()
log.grid_at(1000)                           # numpy array (size, size)
log.rng("world")                            # list of dicts
log.count("steps")                          # rows, from parquet footers
```

A table nothing was written to comes back empty, not missing.

## Archiving

```bash
PYTHONPATH=. python scripts/logs.py list
PYTHONPATH=. python scripts/logs.py show 1
PYTHONPATH=. python scripts/logs.py archive 1 --note "mendel, leak 0.5"
PYTHONPATH=. python scripts/logs.py archive 1 --note "..." --delete
PYTHONPATH=. python scripts/logs.py archives
PYTHONPATH=. python scripts/logs.py restore 1
```

`archive` packs a world into `archives/<name>.tar.gz` with a
`<name>.note.json` next to it (and a copy inside). A note is required.
`--delete` removes the original only after reading the archive back.
