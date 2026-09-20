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

### Checkpoints: continuing a run instead of restarting it
A checkpoint is the whole run in one file (`src/persistence/checkpoint.py`),
not a model file: world grid as it has been eaten, refill clock, every body
(position, energy, age, DNA and the phenotype that DNA was read into), one
full mind per agent (weights, target net **and its counter**, Adam, epsilon,
curiosity visit counts, optionally the replay buffer) and the state of every
named rng stream, plus `schema_version`, the config and the git commit.

- **Restore order is part of the format.** World → minds → rng streams,
  streams LAST, because construction can draw. `RunRandom.load_state`
  restores **in place**: a policy is already holding its generator by then,
  so replacing the objects would restore streams nobody draws from.
- **The replay buffers are most of the file**, so only every
  `checkpoints.replay_every`-th checkpoint carries them. A mind resumed
  without memories refills its buffer from the world.
- **Writes are atomic** (temp file → fsync → `os.replace`): a half written
  checkpoint would look resumable and not be.
- **Two folders, and the folder IS the state**: `checkpoints/rolling/`
  (only the newest `checkpoints.keep` survive) and `checkpoints/pinned/`
  (never deleted by anything). Pinning is moving the file, so a file
  manager does it as well as the CLI does. A prune only ever looks at
  `rolling/`, so pinning four checkpoints does not cost the rolling pool
  one of its `keep` files.

  ```bash
  PYTHONPATH=. python scripts/checkpoints.py list      # numbered
  PYTHONPATH=. python scripts/checkpoints.py pin 3     # number, `latest`,
  PYTHONPATH=. python scripts/checkpoints.py unpin 3   # or part of a name
  ```

  A run can also be pinned before it starts (answer yes to "keep this
  run's final checkpoint"). Pinned checkpoints stay in the resume menu —
  pinning protects a run, it does not retire it.
- **The world outlives the run.** A continued world keeps the id it was born
  with, so agent ids stay in one lineage, and the index counter comes back
  with it (an index names an agent's rng streams — reusing one would hand a
  newborn somebody else's mind). The process gets a **new** run id for its
  log and its checkpoints.
- A resumed run takes its seed, species, world and population from the
  checkpoint, and reads the live `config.yml` for everything tunable
  (life, energy, refill). When the two configs differ the runner says which
  sections changed — an experiment whose rules moved silently is lost.

**Determinism, honestly**: on CPU, same machine, a resume is bit-exact and
so is a re-run of a seed (there is a test for both). Across machines or on
GPU/cuDNN it is "almost" and not an axiom, even with
`run.deterministic: true` (which sets `torch.use_deterministic_algorithms`
with `warn_only`).

### Logging: one folder per world, parquet inside
`RunLog` (`src/persistence/run_log.py`) writes **one folder per WORLD**, not
per process: a run continued from a checkpoint reopens the same folder and
adds a **session** to its header, so ten continuations of one world are ten
entries in one `run.json` and one set of tables.

```
logs/<world_id>[_<label>]/
  run.json     how to repeat it: schema_version, seed per session, config,
               commit, species, gene set, library versions, and one entry
               per session with the steps and episodes it covered
  steps/       a row per agent per tick: position, action, rewards, energy, age
  updates/     a row per gradient update, on the update's own counter
  episodes/agents|population/   one row per window, per agent and for everybody
  events/births|deaths/         a birth with its parents and DNA; a whole life
  world/grid|agents/            the map every `world_snapshot_every` steps
  rng/world.jsonl|agents.jsonl  stream states
```

- **A table is a folder of finished parquet parts.** Parquet only writes its
  footer at `close()`, so a single open file would be unreadable after a
  crash. Each part is written, fsynced and renamed into place;
  `logging.flush_every_steps` bounds what a `kill -9` can cost.
- **Floats are float32**, because a reward has three meaningful digits and
  rounding the text would be cosmetics in the hot loop. Sums, wall clock,
  hashes and rng states are not: those stay float64 or strings, and rng
  never goes near parquet.
- **Every row carries `session`.** A world can be resumed from a checkpoint
  older than rows already on disk, so two rows can honestly claim one step —
  they belong to different continuations.
- **The reader ships with the writer** (`src/persistence/log_reader.py`,
  `RunLogReader`). If you cannot load what you wrote, you did not write it;
  the test writes ten episodes and reads them back. Everything comes back as
  a `pyarrow.Table` (`.to_pandas()` if pandas is installed).
- **An episode is a logging window and nothing else** — `run.episode_length`
  steps, recorded in the header. It resets nothing in the world.
- **The map snapshot keeps objects and bodies apart**: painting the agents
  into the grid would hide the cell each one stands on.
- **Nothing is ever deleted automatically.** A log lives until a human
  decides the experiment is over: `scripts/logs.py archive <n> --note "..."`
  packs a world into `archives/` with a note beside it (outside the tarball
  too, so it can be grepped), and only `--delete` removes the original,
  after reading the archive back.

Each population row carries a `fingerprint`: a rolling hash of every step
logged so far. Same seed → same fingerprints; the first window where two
runs differ is where they diverged.

## Running

```bash
./run.sh                 # tests + normal or visualized run
python src/run.py        # normal run (asks for episodes and seed)
python src/visualized_run.py
PYTHONPATH=. pytest      # tests
```
