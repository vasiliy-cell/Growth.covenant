# Architecture

## The parts, and who owns what

```
config.yml                      every rule and number of a run

src/run.py                      the runner: prompts, the training loop,
                                checkpoints, logging calls
src/visualized_run.py           the same runner with a matplotlib window

src/environment/env.py          GridWorldEnv - one tick of the world:
                                movement, eating, leak, death, aging,
                                birth, refill, observation
src/world/world.py              World - the map's rules: rewards, refill
src/world/Grid_world/map.py     Map - the grid itself: generation, counting,
                                placing objects on empty cells
src/world/Grid_world/objects.py cell ids (0 empty, 1 food, 2 danger,
                                3 = another agent, only in a view)
src/world/Grid_world/reward_for_objects.py   cell id -> reward

src/Agent/AgentManager.py       the registry of bodies: ids, spawning,
                                removal, positions
src/Agent/agent.py              Agent - one body: position, view, energy,
                                age, parents, life summary
src/Agent/life.py               Life - childhood, leak, aging, starvation,
                                stomach ceiling (one object for everybody)
src/Agent/identity.py           run ids and agent ids
src/Agent/State/observation.py  Observation - what an agent sees
src/Agent/State/position.py     Position
src/Agent/Actions/movement/     the 8 moves and which are in bounds

src/Behavior/Choosing_partner.py   who breeds with whom (sexual species)

src/Genome/GenePool.py          genotype and phenotype of every agent
src/Genome/types/factory.py     species name -> species class
src/Genome/types/reuse.py       first genome, mutation, phenotype (shared)
src/Genome/types/clons.py       asexual species
src/Genome/types/non_linear.py  sexual, BLX-alpha blend
src/Genome/types/mendelGenetics.py  sexual, two alleles with dominance

src/Brain/BrainManager.py       the registry of minds: one Brain per agent
src/Brain/brain.py              Brain - act, shape reward, remember, learn
src/Brain/policy/policy.py      epsilon-greedy
src/Brain/q_estimater/mlp.py    the network
src/Brain/q_estimater/trainer.py  Double DQN update, target net, Adam
src/Brain/replay_buffer.py      one agent's memory
src/Brain/reward_shaping/       food bonus + curiosity

src/utils/rng.py                RunRandom - named rng streams from one seed
src/utils/pacing.py             slows the loop down when somebody watches

src/persistence/checkpoint.py        capture / restore a whole run
src/persistence/checkpoint_store.py  rolling/ and pinned/ folders
src/persistence/checkpoint_writer.py one file per mind (archive)
src/persistence/run_log.py           the log writer
src/persistence/log_schema.py        every column of every table
src/persistence/log_reader.py        the log reader

src/visualization/renderer.py   matplotlib window
src/UI/                         the web panel (server, reports, launcher,
                                static pages)
scripts/                        checkpoints.py, logs.py, auto_train.py
tests/                          pytest suite
```

Files that exist but are not used by a run today:
`src/Brain/q_estimater/encoder.py` (an old encoder that fed x, y and raw
cell ids; the runner uses `encode_observation` in `src/run.py`),
`src/utils/td_estimator.py`, `src/Agent/Actions/movement/movements.py`
(`apply_movement`), `src/persistence/archive_writer.py` (empty).

### Boundaries

- **The world never learns who moved.** Everything below the agent (world,
  map, rewards) works with positions. Agent ids only travel upwards, into
  the env API and the logs.
- **The world never sees a brain.** Nothing under `src/world` or
  `src/environment` imports torch. Body and mind meet only through an
  action going in and an observation coming out, joined by the agent id.
- **Two registries, one key.** `AgentManager` holds bodies,
  `BrainManager` holds minds. `BrainManager.sync()` follows the
  population: a new agent gets a mind, a gone agent has its mind saved to
  the archive and dropped.
- **Life rules are one object.** `Life` is built once from `config.yml`
  and shared by every body, so childhood and aging mean the same thing for
  the first agent and the last one.
- **Species is chosen once.** `make_species()` picks the class; nothing
  else branches on the species.

## One tick, end to end

The loop in `src/run.py`, for each global step:

1. **Sync minds.** Every agent without a mind gets its phenotype read
   (`env.make_phenotype`, cached) and a new `Brain`. Minds of agents that
   are gone are saved to `models/<run_id>/<agent_id>.pth` and dropped.
2. **Encode.** Each agent's last observation becomes a one-hot tensor
   (`encode_observation`).
3. **Act.** Each mind runs one forward pass and picks an action,
   epsilon-greedy, among the moves that stay on the map.
4. **World tick** (`env.step(actions)`), in this order:
   1. intent - where each agent wants to go,
   2. resolve - one body per cell; contested cells go to one claimant,
      drawn from the `movement` stream,
   3. apply the moves,
   4. for each agent: add the cell's reward to energy (capped at
      `max_energy`), clear the cell if it held food or danger, pay the
      energy leak,
   5. **death** - adults at or below `death_energy` are removed,
   6. **aging** - every survivor's age goes up by 1,
   7. **birth** - energy-gated reproduction; newborns spawn on random
      free cells,
   8. **refill** - every `world.refill.every` steps, food and danger are
      each topped back up to their share,
   9. observe - one snapshot of positions, one observation per agent.
5. **Learn.** For each agent that acted and is still alive: shape the
   reward (curiosity + food bonus), push the transition into its own
   buffer (`done=False` always), and take one gradient step if the buffer
   is warm. An agent that died this tick is logged but nothing is stored
   for it.
6. **Log** steps, updates, births, deaths, map snapshots, the live frame.
7. **Extinction** - if nobody is alive, the run stops here.
8. **Window boundary** (`step % episode_length == 0`) - rng snapshot,
   episode summary rows, then every mind decays its epsilon and curiosity
   `beta`.
9. **Checkpoint** every `checkpoints.every_steps` steps; **flush** log
   parts every `logging.flush_every_steps` steps.

On any exception (including Ctrl-C and SIGTERM, which is turned into an
exception) the runner writes a rescue checkpoint with replay buffers
before exiting. On a normal end it closes the last partial window, writes
a final checkpoint (pinned if asked) and saves every living mind to the
archive.

A newborn is born at the end of step 4 of tick *t*, appears in the
observations of tick *t*, gets its mind in step 1 of tick *t+1*, and acts
for the first time in tick *t+1*.

## No episodes, no reset, no terminal state

The world is generated once in `GridWorldEnv.start()` and is never
regenerated. Agents are never teleported. Eaten cells stay eaten until a
refill puts something on a random empty cell. There is no terminal state:
`env.step()` returns `(observations, rewards, info)` and every stored
transition has `done=False`. Death is a removal, not a terminal state -
the transition that killed an agent is simply not stored.

## What `env.step()` returns

- `observations` - `{agent_id: Observation}` for every agent alive after
  the tick (newborns included, the dead excluded).
- `rewards` - `{agent_id: env reward}` for every agent that was alive
  when rewards were paid (the dead of this tick included).
- `info`:

| key | meaning |
|---|---|
| `step` | the global step just finished |
| `positions` | `{agent_id: (x, y)}` after the tick |
| `available_actions` | `{agent_id: [move ids]}` after the tick |
| `refilled` | cells added by the refill this tick (0 most ticks) |
| `non_empty_ratio` | share of the map holding food or danger |
| `died` | ids removed this tick |
| `deaths` | one life summary per removed agent (with its genotype) |
| `births` | one record per newborn: id, index, parents, energy, genotype |
| `alive` | population size after the tick |
