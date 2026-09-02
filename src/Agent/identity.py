"""
Agent identity.

An agent id is unique across EVERY run this project has ever made, not just
inside the run that created it. A log line written a year ago must never
name the same agent as a log line written today - that is what makes it
safe to pile years of experiments into one place and compare them.

Uniqueness deliberately does NOT rely on shared state on disk. A counter
file would be the obvious way to hand out consecutive numbers, and it is a
trap: it can be deleted, it forks the moment the repo is cloned to another
machine, and two runs started at the same time race for it. Instead every
run mints its own id, and agent ids are built on top of it:

    run_id   = <date>-<time>-<random token>
    agent_id = <run_id>-<index inside the run>

Two agents can only collide if two runs started in the same SECOND *and*
drew the same 6-hex token (1 in 16.7 million) - and even then only for
agents with the same index.

The date-time prefix is not decoration. Ids sort chronologically, and any
agent id tells you at a glance which experiment it belonged to, so a single
grep pulls the whole population of one run out of a pile of logs.
"""

import uuid
from datetime import datetime

# 6 hex chars = 16.7M tokens. Only runs that start within the same second
# ever compete for one, so this is far more headroom than it looks.
RUN_TOKEN_LENGTH = 6

# Zero padded, so the ids of one run sort by index instead of by digit count.
INDEX_WIDTH = 4


def new_run_id(now=None):
    """Mints the id of a run. Called once per run, never per agent."""
    now = now or datetime.now()
    token = uuid.uuid4().hex[:RUN_TOKEN_LENGTH]

    return f"{now:%Y%m%d-%H%M%S}-{token}"


def make_agent_id(run_id, index):
    """
    Globally unique id of one agent.

    index is the agent's number inside its own run and never repeats there,
    because AgentManager only ever counts upwards - ids are not recycled
    when an agent dies.
    """
    return f"{run_id}-{index:0{INDEX_WIDTH}d}"
