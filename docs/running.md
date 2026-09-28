# Running

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`run.sh` and `panel.sh` use `.venv/bin/python3`. Dependencies: torch,
numpy, pyyaml, pyarrow, matplotlib (visualized run), fastapi + uvicorn
(panel), pytest.

Run everything from the **repo root**. `src/run.py` finds `config.yml`
relative to the repo, but several modules (`src/Genome/types/*.py`,
`src/Behavior/Choosing_partner.py`) open `config.yml` relative to the
current directory.

## Ways to start

```bash
./run.sh                           # asks: run tests? then normal or visualized run
PYTHONPATH=. python src/run.py     # normal run, interactive
PYTHONPATH=. python src/visualized_run.py   # same run + matplotlib window every tick
./panel.sh                         # the web panel (see panel.md)
```

## What `src/run.py` asks

In this order (a question is skipped if its flag is given; without a
terminal every question takes its default):

1. **Continue an earlier run?** - every checkpoint, newest first; 0 = new
   world. A continued world takes its seed, species, population and map
   from the checkpoint, so questions 3-5 are skipped.
2. **Number of episodes** - run length is `episodes * run.episode_length`
   steps. Invalid input = 1.
3. **Number of agents** - default `agents.count`.
4. **Species** - 1 clons, 2 non_linear, 3 mendel; default `genome.type`.
5. **Seed** - a number, or empty / `r` for random.
6. **Name for this experiment** (new worlds only) - becomes part of the
   log folder name.
7. **Keep this run's final checkpoint forever?** - y pins it.

Then it prints the run id, the seed and the log path, and starts.

## Command line flags

| flag | meaning |
|---|---|
| `--episodes N` | logging windows to run |
| `--seed N` | run seed |
| `--agents N` | founders |
| `--species clons\|non_linear\|mendel` | reproduction scheme |
| `--label TEXT` | experiment name |
| `--series TEXT` | groups worlds in `logs/<series>/` |
| `--resume PATH` | continue this checkpoint; `--resume ""` forces a new world |
| `--pin` / `--no-pin` | pin the final checkpoint or not |
| `--live-every N` | rewrite the live frame every N steps (0 = off) |
| `--render N` | run at N steps per second, every step to the live frame |
| `--set KEY=VALUE` | override one config value for this run (repeatable) |

```bash
PYTHONPATH=. python src/run.py --episodes 2000 --agents 20 --species mendel \
    --seed 42 --label "mendel test" --resume "" --no-pin \
    --set life.max_childhood_steps=2000 --set world.size=32
```

`--set` values go through YAML (`2000` is an int, `0.2` a float, `true` a
bool) and are written into the config held by `src/run.py` and the one in
`src/Genome/types/reuse.py`. They are recorded in `run.json` as part of
the session's config. They do **not** reach the separate copies of the
config read by `Choosing_partner.py`, `clons.py` and `mendelGenetics.py`:
an override of `energy.reproduction_threshold` changes who reproduces in
`clons`, but the pairing of the sexual species still reads the value
from the file.

## During a run

Each window prints one line:

```
Episode 12/2000 (world 12) | step=240 | reward=… | per_agent=… | epsilon=… | pop=20 (+1/-0) | filled=0.198
```

plus a line for every birth, death and checkpoint.

- **Ctrl-C** or SIGTERM: a rescue checkpoint is written, then exit code
  130.
- **Extinction**: the run stops as soon as the last agent dies.
- At the end: the last partial window is closed, a final checkpoint is
  written, and every living mind is saved to `models/<run_id>/`.

## Scripts

| script | purpose |
|---|---|
| `scripts/checkpoints.py list\|show\|pin\|unpin` | manage checkpoints (see [checkpoints.md](checkpoints.md)) |
| `scripts/logs.py list\|show\|archive\|archives\|restore` | inspect and archive logs (see [logging.md](logging.md)) |
| `scripts/auto_train.py --runs 5 --episodes 40000` | several runs in a row with fresh seeds; averages `env_reward` over the last `--tail` windows of each run's population table, compares with `--threshold` (GOOD/BAD), appends to `temp_data/results/runs_summary.jsonl` |

`auto_train.py` calls `src.run.main(episodes=…, seed=…)` and leaves the
other prompts to the terminal (agents, species, checkpoint to continue,
label, pin).

## Tests

```bash
PYTHONPATH=. pytest
```

| file | covers |
|---|---|
| `test_life.py` | childhood length, breeding ends childhood, child leak floor, adult death threshold, aging, stomach ceiling, death and birth records |
| `test_multi_agent.py` | one body per cell, contested cells, spawning, local view, view size, curiosity key, one-hot encoding |
| `test_choosing_partner.py` | pairing by energy only, odd one out, one child per tick |
| `test_world_refill.py` | shares at generation, food and danger refilled separately, nothing under a body |
| `test_brain_manager.py` | one mind per agent, sync, minds not shared, minds follow the index, archive on retire |
| `test_s_a_observation.py` | brain acts through the model, learns only when warm, ages per step |
| `test_curiosity.py` | `beta / sqrt(N)`, counts outlive the window, beta decay, keys |
| `test_reward_shaping.py` | food bonus on food only |
| `test_epsilon_decay.py` | epsilon schedule |
| `test_rng.py` | named streams, independence, snapshots restored in place, fresh process |
| `test_checkpoint.py` | bit-exact resume, world and mind restored, schema/species checks, config drift, rolling/pinned rules, atomic save |
| `test_run_log.py` | write/read round trip, crash safety, types, births/deaths, snapshots, sessions, series, live file, header |
| `test_reports_cache.py` | the panel's table cache |
