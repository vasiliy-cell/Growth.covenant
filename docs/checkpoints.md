# Checkpoints

Code: `src/persistence/checkpoint.py`, `checkpoint_store.py`,
`checkpoint_writer.py`, `scripts/checkpoints.py`.

Two different things are saved to disk, and they answer different
questions:

| | checkpoint | model archive |
|---|---|---|
| answers | "where was everybody, what happens next" | "what had this mind learned" |
| scope | the whole run | one agent |
| where | `checkpoints/rolling/`, `checkpoints/pinned/` | `models/<run_id>/<agent_id>.pth` |
| when | every `checkpoints.every_steps`, on crash/stop, at the end | when an agent's mind is retired, and for survivors at the end |
| read back | yes, to continue a world | no |

## What a checkpoint holds

One `torch.save` file, `<run_id>_step<step:09d>.pt`:

- `schema_version` (2 now), `saved_at`, git `commit`, the full `config`,
- `run`: run id, world id, seed, step, episode counter, episode length,
- `env`:
  - the map grid as it has been eaten, its size, the refill period,
  - the global step, the species, the `evolve` list, `view_size`,
  - every body: id, index, position, energy, age, `adult_at`,
    birth step, parents, total reward, number of children,
  - the index counter and the world id,
  - every living agent's genotype **and** phenotype,
- `brains`: per agent - policy net, target net **and its update
  counter**, Adam state, epsilon schedule, curiosity (beta, start beta,
  decay, all visit counts), batch and warm-up sizes, age, and optionally
  the replay buffer,
- `rng`: the state of every used stream,
- `has_replay`.

Replay buffers are most of the file, so only every
`checkpoints.replay_every`-th periodic checkpoint carries them (every 5th
now). The crash/stop checkpoint and the final checkpoint always carry
them. A mind resumed without its buffer is not broken: it refills it
from the world and starts learning again after `min_buffer_size` ticks.

## Restoring: order is part of the format

`Checkpoint.restore`:

1. check the schema version and that the species matches,
2. the world: map, population, genotypes and phenotypes, step counter -
   nothing is generated, nothing is spawned, no stream is touched,
3. the minds: built from the stored phenotypes (so every network has the
   saved shape), then loaded with their saved state,
4. **the rng streams, last** - construction may draw, so the streams are
   put back after it, in place.

What comes from the checkpoint and what from the live `config.yml`:

| from the checkpoint | from the live config |
|---|---|
| seed, species, `evolve` list | `life`, `energy` |
| world id, map (size and contents) | `world.balance`, `world.refill` |
| population, genomes, minds | `reward_shaping.food_bonus` (not saved; every mind uses the live value) |
| `view_size` | logging, checkpoint settings, `episode_length` |

If any top-level config section differs from the saved one, the runner
prints `WARNING: config changed since this checkpoint: <sections>`.

A continued world keeps its world id (agent ids stay in one lineage) and
its index counter. The process gets a new run id for its checkpoint
files, and the log opens a new session in the same folder. A checkpoint
with no living agents is refused ("Extinct").

## Rolling and pinned

```
checkpoints/rolling/   every save lands here; a prune keeps only the
                       newest checkpoint of each of the `keep` most
                       recent RUNS (5 now)
checkpoints/pinned/    never deleted by anything
```

- Pinned = the file is in `pinned/`. Moving the file by hand pins it as
  well as the CLI does.
- The prune looks at `rolling/` only, so pinning does not cost the
  rolling pool a slot.
- Counted by run, not by file: one long run's periodic saves cannot push
  every other run out.
- Loose `.pt` files directly in `checkpoints/` (from before the folder
  split) are treated as rolling.
- Writes are atomic: `<name>.writing` → fsync → `os.replace`.
- A run can be pinned before it starts (the "Keep this run's final
  checkpoint forever?" prompt or `--pin`): its final checkpoint goes to
  `pinned/`.

```bash
PYTHONPATH=. python scripts/checkpoints.py list        # numbered, newest first
PYTHONPATH=. python scripts/checkpoints.py show 3      # opens the file
PYTHONPATH=. python scripts/checkpoints.py pin 3       # number, `latest`,
PYTHONPATH=. python scripts/checkpoints.py unpin 3     # or part of a name
```

An ambiguous name is an error, not a guess.

## When checkpoints are written

- every `checkpoints.every_steps` steps (500 now; 0 = off),
- on any exception, Ctrl-C or SIGTERM (the panel's Stop): a rescue
  checkpoint with replay at the last step. The tick it stopped on may be
  half-applied; the previous periodic checkpoint is always a whole tick,
- at a normal end: a final checkpoint with replay (to `pinned/` if asked).

## Continuing a world

- `python src/run.py` lists every checkpoint first; pick a number, or 0
  for a new world,
- `python src/run.py --resume <path>`,
- the panel's "Continue" button (uses the world's newest checkpoint).

Then only the number of episodes is asked.

## The model archive

`CheckpointWriter` saves one file per agent at
`models/<run_id>/<agent_id>.pth`: agent id, run id, epsilon, curiosity
beta, age and the policy net weights (no Adam state, no target net). It is
written when the mind is retired (the tick after its body died) and for
every living mind at the end of a run, so the dead are on record too, not
only the survivors. Nothing reads these files back.
