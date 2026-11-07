# Probe worlds

A mind in the main run is measured in company: its reward depends on who
ate the food before it, who blocked its way, how hungry it was. A probe
takes a copy of a few adults out of the run and measures each one ALONE,
frozen, on the world its run started from - the same task for every
snapshot, so a curve over snapshots shows how competent the population's
minds became, and nothing else.

## Snapshots, during the run

Every `probe.every_episodes` (N) episodes, on the grid `k*N` of the
world's episodes, `ProbeRecorder` (`src/probe/snapshot.py`) copies Q
(`probe.agents`) distinct living adults - adult as the world means it,
`not agent.is_child()`. Inside one snapshot nobody repeats; the next
snapshot may pick the same agent again.

- **Fewer adults than Q**: wait `probe.rescue_episodes` episodes and try
  once more. Then take everybody there is; nobody means no snapshot. The
  grid does not move because of a rescue: the next try is at `(k+1)*N`.
- **Read-only.** Nothing in the world is touched, and the pick draws from
  a stream of its own, `rng.python("probe")`. A run with snapshots takes
  exactly the steps the same run takes without them (there is a test).
- **What is kept** per agent: the policy net's weights, the phenotype,
  the genotype (for the record) and its current `epsilon` and curiosity
  `beta`. Not energy, age or curiosity visit counts. The file also holds
  the run's seed, config, world size and view.
- A rescue still waiting when the run stops is lost; it is not part of any
  checkpoint.

The snapshots are always written while `every_episodes > 0`. Whether the
probe worlds run right away is asked when the run starts (`--probe` /
`--no-probe`); they can always be run later.

## Probe worlds, after the run

```bash
PYTHONPATH=. python scripts/probe.py list
PYTHONPATH=. python scripts/probe.py run latest   # or a number, or part of a name
```

One probe world per agent per snapshot, run one after another
(`src/probe/runner.py`):

- **the world**: the run's own seed and config, and the map that seed
  generates at step 0 - untouched, not the map the run had eaten. The
  world lives by the same rules: cells pay the same rewards, are cleared
  on contact and are refilled on the same schedule,
- **the body**: one, on the cell the seed's population stream gives the
  first body of the world - every probe of one world starts on the same
  cell. It keeps its agent id and index,
- **no metabolism** (`GridWorldEnv(metabolism=False)`): no energy, leak,
  aging, starvation or birth. A probe always runs exactly
  `probe.episodes` (P) episodes,
- **frozen mind**: no learning and no memories. Epsilon and `beta` start
  where the snapshot found them and decay every episode as they would
  have; the curiosity visit counts start empty, the map being new.

## Where it all lives

```
logs/<world>/probe/
  snapshots/step_<step>.pt          what the run copied
  step_<step>/<agent_id>/           one ordinary log per probe world
```

A probe world's log is a normal world log, read with `RunLogReader`. Its
`run.json` says where the agent came from under `probe` (world, snapshot,
step, agent, its epsilon and beta then). In `steps` the `energy` column is
NaN - there is no energy in a probe world - and `updates` and `deaths`
stay empty.

A probe world is written to `step_<step>/.writing/` and renamed into place
when it is whole, so a folder with a `run.json` is always a finished one.
Running the script again skips those and redoes only what was cut off.

A probe log lives inside its world's folder, so `scripts/logs.py archive`
packs it with the world, and the panel's world list does not show it as a
world of its own.
