# Growth.covenant

DQN agent living in a continuous grid world.

## Working rules

### Comments and docs — English only
Every comment and docstring in the codebase is written in **English**, no
exceptions. This includes comments inside `config.yml` and any new file.
Chat replies to the user stay in the language the user writes in; only the
code is English.

### Commit every important change
Make a git commit for **each important feature or debug fix** — do not pile
several unrelated changes into one commit, and do not leave finished work
uncommitted.

- One logical change = one commit.
- Message: short imperative summary of what changed and why it matters
  (e.g. `refill map instead of regenerating it`, `fix epsilon read from config`).
- Cosmetic-only edits (formatting, typos) do not need their own commit —
  fold them into the related change.

### Clean code
- No commented-out dead code left in files — git history is the archive.
- No copies of an old implementation kept "just in case" at the bottom of a
  module.
- Match the style of the surrounding code: same naming, same section-comment
  layout, same level of comment density.
- Keep responsibilities where they belong: the world owns map rules, the env
  owns the step loop, the brain owns learning, the logger owns log format.

## Architecture (what matters when changing things)

### One continuous run, no episodes in the world
The world is generated **once** in `GridWorldEnv.start()` and is never reset:

- the agent is created once and keeps its position for the whole run — it is
  never teleported back to the start of the map,
- eaten cells stay eaten; instead of regeneration the map tops itself up
  (`World.maybe_refill` → `Map.refill`): every `world.refill.every` steps, if
  colored cells drop below `world.refill.threshold`, `world.refill.amount`
  random objects are added to empty cells,
- there is no terminal state, so `env.step()` returns `(observation, reward,
  info)` and the training loop always stores `done=False`.

### "Episode" = logging window only
An episode no longer affects the world. It only:

- flushes an `episode_summary` line to the log,
- decays `policy.epsilon` (`Policy.next_episode`) and curiosity
  (`RewardShaping.reset`).

`run.episode_length` comes from `config.yml`; the number of episodes is asked
in the terminal before the run starts.

### Config
`config.yml` lives in the **repo root** (it drives the world, logging and run
length, not only the brain) and is resolved relative to the repo root, so it
works from any working directory.

### Logging
`Logger` is run-scoped: **one file per run**, `logs/run_<timestamp>.jsonl`.

- `run_info` — once, global seed and run parameters,
- `step` — one per step, `step` is the global step index,
- `episode_summary` — one per logging window, keeps the historical field
  names so all visualizers keep working.

Full RNG states (python `random`, numpy, torch, cuda) are snapshotted once per
`logging.rng_snapshot_every` episodes into `logs/rng/<run>.jsonl`. There are no
per-episode local seeds anymore — those snapshots are the only way to replay a
run from a given window. They are heavy (~24 KB per snapshot), so raise
`rng_snapshot_every` for long runs.

Anything that used to treat "one log file = one episode" must group steps by
their `episode` field instead (`visualization/logs_visualization/episode_grouping.py`).

## Running

```bash
./run.sh                 # tests + normal or visualized run
python src/run.py        # normal run (asks for episodes and seed)
python src/visualized_run.py
PYTHONPATH=. pytest      # tests
```
