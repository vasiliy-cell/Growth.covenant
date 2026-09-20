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

- an agent keeps its position for as long as it lives — it is never
  teleported back to the start of the map,
- eaten cells stay eaten; instead of regeneration the map tops itself up
  (`World.maybe_refill` → `Map.refill`): every `world.refill.every` steps, if
  colored cells drop below `world.refill.threshold`, `world.refill.amount`
  random objects are added to empty cells,
- there is no terminal state, so `env.step()` returns `(observation, reward,
  info)` and the training loop always stores `done=False`.

### Life: childhood, aging, starvation
The population turns over even though the world does not. The rules live in
`src/Agent/life.py` (one `Life` object shared by everybody, built from the
`life` / `energy` sections of `config.yml`); an agent carries only its own
`age` and asks `Life` what that age costs it:

- **childhood** — the first `life.childhood_steps` ticks after birth. The
  agent ages and leaks energy, but nothing can kill it,
- **adulthood** — mortal. At or below `life.death_energy` the agent starves
  and `GridWorldEnv._reap()` removes it from the run,
- **aging** — the personal leak is `energy.energy_leak` plus
  `life.aging.amount` for every full `life.aging.every` ticks lived, so
  there is no hard age limit: the bill simply keeps rising,
- a body is born with `energy.start_energy` (a newborn gets
  `energy.reproduction_cost` from its parents instead).

Order inside a tick: eat → leak → **death** → age → birth. Death before
birth, so a starving agent does not reproduce on its last tick; aging after
death, so childhood really is `childhood_steps` whole ticks.

`info` from `env.step()` carries `died` (ids that left this tick) and
`alive`. An agent in `died` has no next observation, so `src/run.py` logs
its final step but stores nothing for it, and the run ends early when the
last agent starves.

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

### Randomness: named streams, one seed
Every draw in a run comes from `RunRandom` (`src/utils/rng.py`), asked for
by name: `rng.python("world")`, `rng.numpy("genome")`, `rng.torch("agent",
7, "policy")`. Streams are derived from the run seed through
`SeedSequence`, so they are independent — a fight over a cell cannot move
the next refill, and a birth cannot move anybody's exploration.

- world / population / movement / genome are the world's streams,
- every mind gets `agent/<index>/brain` (weights, through a forked global
  torch state — torch takes no generator for layer init), `agent/<index>/
  policy` (exploration) and `agent/<index>/replay` (batch sampling),
- an agent's streams follow its **index**, never the order of birth, so a
  run stays reproducible through births and deaths.

Nothing may reach for a global generator (`random.sample`, `torch.rand`,
`np.random.*`) — that is exactly what made runs unreproducible before. New
randomness gets a new name.

`rng.state()` snapshots every live stream and `load_state()` puts them
back, in this process or a fresh one: that is the half of a checkpoint that
is not weights.

### Logging
`Logger` is run-scoped: **one file per run**, `logs/run_<timestamp>.jsonl`.

The log is flushed on the header, on every window summary and every
`logging.flush_every` steps, so a run that is killed keeps everything but
its last few steps. Each `episode_summary` also carries a `fingerprint`: a
rolling hash of every step logged so far. Same seed → same fingerprints;
the first window where two runs differ is where they diverged.

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
