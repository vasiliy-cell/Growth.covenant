# The brain

Code: `src/Brain/`, `encode_observation` in `src/run.py`.

Every agent has its own `Brain`. Nothing about learning is shared: not the
network, not the replay buffer, not epsilon, not curiosity. Every number
that shapes a mind comes from the agent's **phenotype** (see
[genome.md](genome.md)), except `reward_shaping.food_bonus`, which is one
config value for everybody.

```
Brain
├── trainer        DQNTrainer: policy net, target net, Adam, Double DQN
├── policy         Policy: epsilon-greedy with the agent's own torch stream
├── replay_buffer  ReplayBuffer: the agent's own memories
├── reward_shaping RewardShaping: food bonus + Curiosity
├── batch_size, min_buffer_size
└── age            transitions stored so far
```

## What the network sees

`encode_observation(obs)` turns the agent's `local_view` (see
[world.md](world.md#what-an-agent-sees)) into a flat float vector,
one-hot by cell kind, channel after channel:

```
[ food? x 121 | danger? x 121 | another agent? x 121 | off the map? x 121 ]
```

For an 11 x 11 window that is 4 x 121 = **484 inputs**. An empty cell is
all four channels at 0. The channel order is `CELL_CHANNELS = (1, 2, 3, -1)`.

Not in the input: the agent's position, its energy, its age. Position was
removed because in a world refilled at random, "where am I" says nothing
about where food is, and raw 0..63 numbers dominated the input. One-hot
replaced raw cell ids because as one number, danger (2) read as "twice
the food".

## The network

`MLP`: `hidden_layers` blocks of `Linear -> ReLU`, each `hidden_size`
wide, then a `Linear` to **8 outputs**, one Q value per move. With
`hidden_layers = 0` the network is a single linear layer.

Both numbers are genes, rounded to integers when the phenotype is read,
so network shape can differ between agents.

Initial weights are torch's default layer init, drawn inside a forked
global torch state seeded from the agent's `agent/<index>/brain` seed (see
[randomness.md](randomness.md)).

## Acting: epsilon-greedy

`Policy.select_action(q_values, available_actions)`, once per tick:

- with probability `epsilon` - a uniformly random move among the
  available ones (moves that stay on the map),
- otherwise - the available move with the highest Q value.

Q values are computed every tick either way (one forward pass, no
gradient). Both draws come from the agent's own `agent/<index>/policy`
torch generator.

`epsilon` starts at the agent's gene value and is multiplied by
`epsilon_decay` at every logging window boundary, never going below
`epsilon_min`. The schedule follows the **agent's** life: a newborn starts
from its own starting epsilon while older agents are already exploiting.

## Reward: what the mind learns from

`RewardShaping.compute(next_observation, env_reward)` after every tick:

```
intrinsic = curiosity.step(next_observation)            (beta / sqrt(N))
          + food_bonus  if env_reward > 0               (5 now)
shaped    = env_reward + intrinsic
```

- `env_reward` is what the world paid: +5, -5 or 0. Energy follows only
  this.
- `food_bonus` makes food louder to the mind: food is learned as
  5 + 5 = +10 (plus curiosity) against danger's -5. With both at 5,
  touching any cell was a zero-sum bet and avoiding everything was the
  safe optimum.

The shaped reward is what goes into the replay buffer.

### Curiosity

`Curiosity` counts how many times this agent has seen each state:

- key = `(position, map_view)` - the agent's (x, y) and the window of
  **objects only**. Other agents are left out: they move every tick, and a
  key including them would almost never repeat, so curiosity would never
  decay,
- on every step the count of the new state goes up by one, and the
  intrinsic reward is `beta / sqrt(N)`: `beta` on the first visit,
  `beta / 1.41` on the second, `beta / 2` on the fourth, and so on,
- counts are personal (a newborn finds the whole map new) and **last the
  agent's whole life** - they are never cleared,
- `beta` starts at the `curiosity_beta` gene and is multiplied by
  `curiosity_decay` at every logging window boundary. It has no floor.

Because the key contains the position and the objects around it, the
same place with one food eaten nearby is a new state.

Counts used to be cleared every window. That made almost every step new
again, so curiosity paid about `beta` on every step forever.

## Remembering

`Brain.remember` pushes `(state, action, shaped_reward, next_state,
done=False)` into the agent's replay buffer and increases `Brain.age`.

- One transition per tick per agent, so `buffer_size` and
  `min_buffer_size` are counted in ticks of this agent's own history.
- The buffer is a `deque` with `maxlen = buffer_size`: the oldest
  transition drops out when it is full.
- `done` is always False: the world has no terminal state. An agent that
  dies on a tick stores nothing for that tick.

## Learning: Double DQN

`Brain.learn()` runs **once per tick per agent**, right after
`remember`:

- if the buffer holds fewer than `min_buffer_size` transitions: nothing
  (no update row in the log),
- otherwise: sample `batch_size` transitions **without replacement** with
  the agent's `agent/<index>/replay` stream, and call
  `DQNTrainer.update`.

`DQNTrainer.update`:

```
Q(s, a)        = policy_net(s)[a]
a*             = argmax_a' policy_net(s')[a']        policy net chooses
target         = r + gamma * target_net(s')[a*] * (1 - done)
loss           = MSE(Q(s, a), target)                mean over the batch
```

then `zero_grad`, `backward`, gradient clipping with
`clip_grad_norm_(max_norm)`, one Adam step with `learning_rate`, and
`training_step += 1`. Every `target_update_freq` updates the target net
is overwritten with the policy net (a hard copy, no soft update).

Returned for the log (means over the batch): `loss`, `td_error`
(target - Q), `grad_norm` (before clipping), `target_q`, `q_prediction`.

Since there is no terminal state, a state's value is roughly
`reward per step / (1 - gamma)`: at gamma = 0.99 about 100 steps' worth.

## The logging window boundary

At every `step % run.episode_length == 0`, `BrainManager.next_episode()`
calls, for every mind:

- `epsilon = max(epsilon * epsilon_decay, epsilon_min)`
- `beta = beta * curiosity_decay`

Nothing else in a brain depends on windows.

## Lifecycle of a mind

- **Born**: at the start of the tick after the body's birth (or at the
  first tick for founders), `BrainManager.sync` reads the phenotype and
  builds the brain from the agent's index streams.
- **Retired**: at the start of the tick after the body's death, `sync`
  saves `Brain.state()` - epsilon, curiosity beta, age and the policy net
  weights - to `models/<run_id>/<agent_id>.pth` and drops the brain.
  Minds still alive at the end of a run are saved the same way.
- **Checkpointed**: `Brain.full_state()` - weights, target net, Adam
  state, training step counter, epsilon schedule, curiosity (beta and all
  visit counts), `batch_size`, `min_buffer_size`, age, and optionally the
  replay buffer. See [checkpoints.md](checkpoints.md).

## Genes used by the brain

| gene | used as |
|---|---|
| `learning_rate` | Adam lr |
| `max_norm` | gradient clip norm |
| `gamma` | discount |
| `target_update_freq` | updates between target net copies |
| `hidden_size`, `hidden_layers` | network shape |
| `buffer_size` | replay capacity |
| `batch_size` | transitions per update |
| `min_buffer_size` | transitions before the first update |
| `epsilon`, `epsilon_decay`, `epsilon_min` | exploration schedule |
| `curiosity_beta`, `curiosity_decay` | curiosity strength and fade |

`alpha` and `sigma` are genes of reproduction, not of the brain.
