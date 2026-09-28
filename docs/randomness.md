# Randomness

Code: `src/utils/rng.py` (`RunRandom`).

Every random draw in a run comes from a **named stream** derived from the
one run seed. Nothing may use a global generator (`random.*`,
`np.random.*`, `torch.rand` without a generator): that is what made runs
unreproducible before.

## How a stream is made

```
stream("python", "agent", 7, "policy")
  -> SeedSequence(entropy = run seed,
                  spawn_key = (crc32("python"), crc32("agent"), 7, crc32("policy")))
  -> random.Random / np.random.Generator / torch.Generator
```

- The **kind** (`python`, `numpy`, `torch`) is part of the name:
  `numpy("world")` and `python("world")` are different streams.
- Names are hashed with `crc32`, not Python's `hash()` (which changes
  per process).
- Streams are cached: asking twice returns the same generator object.
- Streams are independent: draining one never moves another. A fight over
  a cell cannot shift the next refill; one more birth cannot shift anybody
  else's exploration.

## The streams of a run

| stream | used for |
|---|---|
| `python:world` | map generation, refill placement |
| `python:population` | spawn positions (founders and newborns) |
| `python:movement` | winner of a contested cell |
| `numpy:genome` | founders' genomes, mutation, blending, mendel inheritance |
| `numpy:agent/<index>/phenotype` | mendel's coin toss for equal dominance letters |
| `seed:agent/<index>/brain` | a seed for the network's initial weights |
| `torch:agent/<index>/policy` | epsilon-greedy draws |
| `python:agent/<index>/replay` | replay batch sampling |

An agent's streams follow its **index**, never its birth order or its
position in any list, so agent 7 gets the same mind whether it was born
into a crowd or alone.

Network weights: torch layers take no generator, so `BrainManager`
forks the global torch state, seeds it with `seed_for("agent", index,
"brain")`, builds the network, and restores the global state.

As a safety net the runner also seeds the global generators
(`np.random.seed`, `torch.manual_seed`) from the run seed, but nothing
should rely on them.

## The seed

- Asked in the terminal (empty or `r` = random), or `--seed N`.
- A random seed is `int(time.time() * 1e6)`.
- Written to `run.json` (per session) and to every checkpoint.
- A continued world uses the seed stored in its checkpoint.

## Snapshots

- `rng.state(scope)` returns every stream that has been used, as JSON-able
  values; `scope` is `"all"`, `"world"` (names not starting with
  `agent`) or `"agents"`.
- `rng.load_state(states)` restores them **in place** - the generator
  objects already held by policies and buffers are rewound, not replaced.
  Replacing them would restore streams nobody draws from.
- Checkpoints carry all streams. The log writes the world streams every
  `logging.rng_world_every_episodes` windows and the agents' streams every
  `logging.rng_agents_every_episodes` windows (about 16 KB per agent, and
  random bytes do not compress), to `rng/world.jsonl` and
  `rng/agents.jsonl`.

## Determinism, honestly

- On CPU, same machine: a re-run of a seed and a resume from a checkpoint
  are bit-exact (there are tests for both).
- Across machines or on GPU: "almost", not guaranteed, even with
  `run.deterministic: true` (which calls
  `torch.use_deterministic_algorithms(True, warn_only=True)`).
- The `fingerprint` column of `episodes/population` is a rolling hash of
  every logged step. Same seed → same fingerprints; the first window where
  two runs differ is where they diverged.
