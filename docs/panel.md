# The panel

Code: `src/UI/` (`server.py`, `reports.py`, `launcher.py`, `static/`),
`panel.sh`.

A local web app for watching runs, reading their logs and starting new
ones.

```bash
./panel.sh               # (re)starts the server on http://127.0.0.1:8000 and opens a browser
./panel.sh --no-browser  # server only
```

It binds to 127.0.0.1 only and has no authentication. It can start
processes and delete data.

## How it relates to a run

- The panel only **reads** what runs write: finished parquet parts,
  `run.json` and the live frame `.panel/live/<world_id>.json`. A run does
  not know the panel exists.
- A run started from the panel is a separate `src/run.py` process with
  every prompt answered by flags. Runs are queued and go **one at a time**;
  "repeat N" queues N runs (with a given seed, seed, seed+1, ...; without
  one, a random seed each).
- **Watching** a world writes `.panel/watch/<world_id>.json` with a speed
  and a deadline; the run slows to that many steps per second and writes
  every step to the live frame. The live view renews the request every
  2 s; a closed tab lets it lapse after 6 s and the run goes back to full
  speed.
- **Stop** sends SIGTERM to the run's pid (after checking it really is a
  `src/run.py` process); the run writes a rescue checkpoint and exits.
- Consoles of launched runs are in `.panel/consoles/`.
- `.panel/` is never inside `logs/`: it is a view of runs, not a record.

## Pages

| page | address | what it shows |
|---|---|---|
| Worlds | `#/` | catalog of every world: label, species, sessions, size, population, whether it runs, whether it can be continued |
| World | `#/world/<id>` | one world: details and rules, reward and learning charts (filterable by cohort - children / adults - and by lifespan), family tree, leaderboard, per-agent life and heat map, world heat map; actions: continue, keep (pin), rename, stop, archive, delete |
| Compare | `#/compare` | several worlds side by side on one metric |
| Launch | `#/launch` | form: episodes, agents, species, seed, label, pin, repeat; the run queue and consoles |
| Live | `#/live/<id>` | the map and bodies as the run writes them, with a speed control |

Charts are built from the per-window tables, never from the step table.
Tables are cached until their folder changes on disk.

### Derived numbers

Some charts compute things that are not logged columns:

- **when an agent's childhood ended** - the age of its first child (from
  `events/births`), or `max_childhood_steps` from the newest session's
  config, whichever is smaller - the same rule as `Life.adulthood`,
- **leak per window** (reward charts with leak on) - `Life.leak` redone in
  arrays from the session config: base leak for children, base + aging
  steps for adults, times the ticks the agent was logged in the window,
  using the age at the end of the window,
- **lifespan** - from the death row, or the oldest logged age for agents
  still alive.

## API (for reference)

| method | path | |
|---|---|---|
| GET | `/api/worlds` | catalog |
| GET | `/api/facets` | config values that differ between worlds |
| GET | `/api/worlds/{w}/details` | header, sessions, rules, live state |
| GET | `/api/worlds/{w}/rewards?cohort&min_steps&max_steps&leak` | reward charts |
| GET | `/api/worlds/{w}/learning?cohort&min_steps&max_steps` | learning charts |
| GET | `/api/worlds/{w}/family` | family tree |
| GET | `/api/worlds/{w}/leaderboard?by&limit` | top agents |
| GET | `/api/worlds/{w}/agent/{agent_id}` | one agent's life |
| GET | `/api/worlds/{w}/heatmap` | where agents have been |
| GET | `/api/worlds/{w}/stream` | live frames (server-sent events) |
| POST | `/api/worlds/{w}/watch` | slow the run down while watched |
| POST | `/api/worlds/{w}/stop` | SIGTERM the run |
| POST | `/api/worlds/{w}/keep` | pin the newest checkpoint |
| POST | `/api/worlds/{w}/rename` | new label and folder name (not while running) |
| POST | `/api/worlds/{w}/continue` | queue a run from the newest checkpoint |
| POST | `/api/worlds/{w}/archive` | tar.gz with a note, optionally delete |
| DELETE | `/api/worlds/{w}` | delete the log folder (not while running) |
| POST | `/api/compare` | compare worlds on a metric |
| GET | `/api/metrics` | available comparison metrics |
| GET/POST | `/api/runs` | queue / launch |
| GET | `/api/runs/{id}/world`, `/api/runs/{id}/console` | a launched run's world and console |
| DELETE | `/api/runs/{id}` | stop a launched run |
| POST | `/api/runs/clear` | forget finished runs |
| GET | `/api/config` | the current config |
