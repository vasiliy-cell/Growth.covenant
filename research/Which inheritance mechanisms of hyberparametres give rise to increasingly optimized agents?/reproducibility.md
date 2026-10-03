# Reproducibility

Research question: *Which inheritance mechanisms of hyperparameters give rise
to increasingly optimized agents?*

## Main metric

**Env reward per adult agent** - per logging window (`run.episode_length`
steps): the sum of `env_reward` over the adult agent-windows of that window,
divided by the number of adult agent-windows in it. This is the panel's
reward chart with cohort `adults` and mode `per agent`
(`src/UI/reports.py: rewards(reader, cohort="adult")`, divided by `agents`).
An agent is adult from `min(first child, life.max_childhood_steps)` on.

## Seeds

These 15 seeds are used for every run of this research, and no others.

| # | seed |
|---|---|
| 1 | 1290435116 |
| 2 | 4253778242 |
| 3 | 301112939 |
| 4 | 2753460196 |
| 5 | 1809987412 |
| 6 | 914445736 |
| 7 | 2151682457 |
| 8 | 2974571302 |
| 9 | 588057067 |
| 10 | 1226380944 |
| 11 | 2083014961 |
| 12 | 703876974 |
| 13 | 2738809320 |
| 14 | 4232660768 |
| 15 | 2482739106 |

Derived once, so the list itself can be regenerated:

```python
import numpy as np
np.random.SeedSequence(20261003).generate_state(15, dtype=np.uint32).tolist()
```

Pass one with `python src/run.py --seed <seed>` or type it at the seed prompt.

## Code

- current commit: `5ff034b46e7f7b1085794e59ea2f4ee36ab56845`
  (baseline config: every gene frozen, `genome.evolve: []`)
- every run also records its own commit, config, seed and library versions
  in `logs/<world_id>/run.json`

## Experiments

### Baseline - every gene frozen

Multi-agent with reproduction, no gene ever varies or mutates: every agent
carries the `mean` of each gene (`genome.evolve: []`, commit `5ff034b`).
40000 episodes per seed, all 15 seeds, logs in `logs/baseline/<world_id>_baseline-s<n>/`
(series `baseline`). Started 2026-10-03, 6 runs at a time, torch on one
thread per process:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python src/run.py \
  --episodes 40000 --seed <seed> --agents 20 --species clons \
  --label baseline-s<n> --series baseline --resume "" --no-pin
```

Note: `evolve` with every entry commented out is read as `None`, and the
env treats `None` as "evolve every gene". Freezing them takes `evolve: []`.

## Machine

- macOS 15.6 (build 24G84), Apple Silicon (arm64)
- device: CPU (CUDA not available; MPS available but not used)
- torch threads: 4 intra-op, 10 inter-op by default; the experiment runs
  set `OMP_NUM_THREADS=1` (a bit-exact re-run must use the same)
- `run.deterministic: true`

## Python and libraries

Python 3.9.6, virtual environment `.venv`.

Libraries the experiment depends on:

| library | version |
|---|---|
| torch | 2.8.0 |
| numpy | 2.0.2 |
| pyarrow | 21.0.0 |
| PyYAML | 6.0.3 |

Analysis, panel and tests:

| library | version |
|---|---|
| matplotlib | 3.9.4 |
| torchvision | 0.23.0 |
| fastapi | 0.128.8 |
| uvicorn | 0.39.0 |
| starlette | 0.49.3 |
| pydantic | 2.13.5 |
| pytest | 8.4.2 |

Full `pip freeze` of `.venv`:

```
annotated-doc==0.0.5
annotated-types==0.7.0
anyio==4.12.1
click==8.1.8
contourpy==1.3.0
cycler==0.12.1
exceptiongroup==1.3.1
fastapi==0.128.8
filelock==3.19.1
fonttools==4.60.2
fsspec==2025.10.0
h11==0.16.0
idna==3.20
importlib_resources==6.5.2
iniconfig==2.1.0
Jinja2==3.1.6
kiwisolver==1.4.7
MarkupSafe==3.0.3
matplotlib==3.9.4
mpmath==1.3.0
networkx==3.2.1
numpy==2.0.2
packaging==26.2
pillow==11.3.0
pluggy==1.6.0
pyarrow==21.0.0
pydantic==2.13.5
pydantic_core==2.46.5
Pygments==2.20.0
pyparsing==3.3.2
pytest==8.4.2
python-dateutil==2.9.0.post0
PyYAML==6.0.3
six==1.17.0
starlette==0.49.3
sympy==1.14.0
tomli==2.4.1
torch==2.8.0
torchvision==0.23.0
typing-inspection==0.4.2
typing_extensions==4.15.0
uvicorn==0.39.0
zipp==3.23.1
```
