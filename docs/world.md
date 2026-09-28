# The world

Code: `src/world/`, `src/environment/env.py`, `src/Agent/agent.py`,
`src/Agent/AgentManager.py`.

## The map

A square grid of `world.size` x `world.size` cells (64 x 64 = 4096 now).
Coordinates are `(x, y)`, x to the right, y down; the grid is stored as
`grid[y, x]`. Each cell holds one object:

| id | name | reward = energy change | colour |
|---|---|---|---|
| 0 | empty | 0 | - |
| 1 | food | +5 | green |
| 2 | danger | -5 | red |

A fourth value, `3` (`AGENT_CELL`), exists only in what an agent sees: the
map itself never holds a body.

### Generation (once per world)

`Map._generate`, with the `world` rng stream:

1. for each kind, `int(size * size * share)` cells of that kind
   (`world.balance.food`, `world.balance.danger`) - 409 food and 409
   danger with the current 0.10 / 0.10 on 64 x 64,
2. every other cell is empty,
3. if a kind got zero cells (a tiny map or a tiny share), one random cell
   is set to it, so every kind appears at least once,
4. the list is shuffled and reshaped into the grid.

`world.balance` must not add up to more than 1, or `World` refuses to
start.

### Eating

When an agent stands on a food or danger cell after moving, it receives
the cell's reward and the cell becomes empty. Standing still on an empty
cell pays 0. Because there is one body per cell, two agents never share a
cell's reward.

### Refill

`World.maybe_refill`, called once per tick after births. On every step
where `step % world.refill.every == 0` (every 5 steps now):

- for food and for danger **separately**: target = `int(share * size^2)`,
  missing = target - current count,
- if missing > 0, that many cells of that kind are placed on random empty
  cells (sampled without replacement from the `world` stream),
- cells where an agent stands are excluded, so nothing appears under a
  body.

The map is never regenerated. Food eaten in one corner comes back at
random places across the whole map, not where it was eaten. The two kinds
are counted apart on purpose: counted together, agents that avoid danger
and eat food drifted the map towards mostly danger while the total stayed
"full".

The refill clock is the global step, so on a continued run it keeps the
same phase.

## Bodies on the map

### Spawning

`AgentManager._spawn_position`, with the `population` stream: up to 100
random cells are tried until one is free of bodies; if all fail, the grid
is scanned row by row for the first free cell; if the map is full of
bodies, spawning raises an error. A spawn does not look at objects: an
agent can be born on a food or danger cell. That cell is not paid at
birth. Rewards are paid for the cell an agent stands on after the moves of
a tick, so the spawn cell is paid only if the agent's first move is
refused and it stays there.

The first population is spawned in `env.start()`. Newborns are spawned the
same way, on a random free cell anywhere on the map - **not** next to their
parents.

### Moves

Eight moves, no "stay" action:

| id | move | (dx, dy) |
|---|---|---|
| 0 | up | (0, -1) |
| 1 | down | (0, +1) |
| 2 | left | (-1, 0) |
| 3 | right | (+1, 0) |
| 4 | up-left | (-1, -1) |
| 5 | up-right | (+1, -1) |
| 6 | down-left | (-1, +1) |
| 7 | down-right | (+1, +1) |

A mind only chooses among moves that keep it on the map
(`get_available_movements`). The world has no walls apart from the edge.

### Resolving a tick's moves

`GridWorldEnv._resolve_movements` - the only place the movement rule
lives. All agents move **simultaneously**:

1. every agent states where it wants to go,
2. one snapshot of occupied cells is taken **before anybody moves**,
3. a target that is occupied in that snapshot is refused: the agent stays
   where it is. This includes a cell whose owner is leaving this very
   tick - a column of agents advances one cell per tick,
4. a free target claimed by one agent is granted,
5. a free target claimed by several agents goes to one of them, chosen by
   `movement_rng.choice(claimants)`; the others stay put.

Nobody gains from being earlier in the agent list. A refused move is not
punished by itself: the agent stays where it is, is paid for that cell
again, and pays the leak. The cell it stands on was emptied when it
arrived, and a refill never places anything under a body, so a blocked
agent earns 0 (the one exception is the spawn cell above).

## What an agent sees

`Agent.get_state` builds an `Observation` after the tick has settled, from
one shared snapshot of positions, so every agent sees the same frame.

- The window is centred on the agent and reaches `view_size // 2` cells to
  each side. `view_size: 10` gives `10 // 2 = 5`, so the window is
  **11 x 11** (an even `view_size` is effectively rounded up).
- Cells outside the map read as `-1`.
- `map_view` - the window with objects only (0, 1, 2, -1).
- `local_view` - the same window with every other agent painted as `3`
  over whatever it stands on. The agent's own cell (the centre) is never
  painted.
- `position` - the agent's `(x, y)`.

What the network receives is `local_view` only, one-hot (see
[brain.md](brain.md#what-the-network-sees)); the position is **not** an
input. Curiosity uses `position` + `map_view` as the key of a state (see
[brain.md](brain.md#curiosity)).

A body hides the object it stands on in `local_view`. That is a real loss
of information, accepted in exchange for a single cell value per body.

## Parameters in play

| key | now | effect |
|---|---|---|
| `world.size` | 64 | side of the map |
| `world.balance.food` | 0.10 | food share at generation and refill target |
| `world.balance.danger` | 0.10 | danger share at generation and refill target |
| `world.refill.every` | 5 | refill check period in steps |
| `agents.view_size` | 10 | window side (11 x 11 effective) |

On a continued world, the map size and `view_size` come from the
checkpoint (the saved networks were sized to them); `balance` and
`refill.every` come from the live `config.yml`.
