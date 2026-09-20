"""
Every column this project writes, in one place.

Two rules run through all of it:

  - floats are float32. A reward is a number with three meaningful digits
    and no business taking 8 bytes; rounding the text instead would be
    cosmetics and would cost work in the hot loop, while a type costs
    nothing and halves the file.
  - except where precision is the point: SUMS (a window's reward is
    thousands of additions), WALL CLOCK (a unix timestamp needs the
    mantissa) and anything hashed or random. Those are float64 or strings,
    and rng states never go near parquet at all.

Every row carries `session`, the index of the continuation that wrote it.
A world can be picked up from a checkpoint any number of times, including
from a checkpoint older than rows already on disk, so two rows can honestly
claim the same step - they belong to different continuations of the same
world, and the session tells them apart.
"""

import pyarrow as pa

SCHEMA_VERSION = 1

# Where a step happened and what it paid - one row per agent per tick.
STEPS = pa.schema([
    ("step", pa.int64()),
    ("session", pa.int16()),
    ("wall_clock", pa.float64()),
    ("agent_id", pa.string()),
    ("x", pa.int16()),
    ("y", pa.int16()),
    ("action", pa.int8()),
    ("env_reward", pa.float32()),
    ("intrinsic_reward", pa.float32()),
    ("shaped_reward", pa.float32()),
    ("energy", pa.float32()),
    ("age", pa.int32()),
])

# One row per gradient update, on the update's own clock: a mind that is
# still warming up its buffer takes steps without ever appearing here.
UPDATES = pa.schema([
    ("step", pa.int64()),
    ("session", pa.int16()),
    ("wall_clock", pa.float64()),
    ("agent_id", pa.string()),
    ("training_step", pa.int64()),
    ("loss", pa.float32()),
    ("grad_norm", pa.float32()),
    ("td_error", pa.float32()),
    ("target_q", pa.float32()),
    ("q_prediction", pa.float32()),
    ("curiosity_beta", pa.float32()),
    ("epsilon", pa.float32()),
    ("buffer_size", pa.int32()),
])

# An episode is a logging window and nothing else. Per agent...
EPISODE_AGENTS = pa.schema([
    ("episode", pa.int32()),
    ("session", pa.int16()),
    ("step_start", pa.int64()),
    ("step_end", pa.int64()),
    ("agent_id", pa.string()),
    ("steps", pa.int32()),
    ("env_reward", pa.float64()),
    ("intrinsic_reward", pa.float64()),
    ("shaped_reward", pa.float64()),
    ("epsilon", pa.float32()),
    ("curiosity_beta", pa.float32()),
    ("energy", pa.float32()),
    ("age", pa.int32()),
])

# ...and once for the whole population, which is the row you plot first.
EPISODE_POPULATION = pa.schema([
    ("episode", pa.int32()),
    ("session", pa.int16()),
    ("step_start", pa.int64()),
    ("step_end", pa.int64()),
    ("wall_clock", pa.float64()),
    ("duration", pa.float64()),
    ("agents", pa.int32()),
    ("births", pa.int32()),
    ("deaths", pa.int32()),
    ("steps", pa.int64()),
    ("env_reward", pa.float64()),
    ("intrinsic_reward", pa.float64()),
    ("shaped_reward", pa.float64()),
    ("updates", pa.int64()),
    ("mean_loss", pa.float64()),
    ("mean_td_error", pa.float64()),
    ("mean_epsilon", pa.float32()),
    ("mean_curiosity_beta", pa.float32()),
    ("non_empty_ratio", pa.float32()),
    ("fingerprint", pa.string()),
])

# A birth: who made it, and what it was made with. The genotype is JSON
# because a mendel genome is pairs of alleles and does not flatten; the
# phenotype does flatten, and those columns are what you filter a
# population by, so they are real columns - see births().
BIRTHS_HEAD = [
    ("step", pa.int64()),
    ("session", pa.int16()),
    ("wall_clock", pa.float64()),
    ("agent_id", pa.string()),
    ("index", pa.int32()),
    ("parents", pa.list_(pa.string())),
    ("energy", pa.float32()),
    ("genotype_json", pa.string()),
]

# A death: the whole life in one row, because nothing else in the logs can
# answer "what happened to this one" without a join across a million rows.
DEATHS = pa.schema([
    ("step", pa.int64()),
    ("session", pa.int16()),
    ("wall_clock", pa.float64()),
    ("agent_id", pa.string()),
    ("index", pa.int32()),
    ("parents", pa.list_(pa.string())),
    ("birth_step", pa.int64()),
    ("death_step", pa.int64()),
    ("lifespan", pa.int64()),
    ("cumulative_reward", pa.float64()),
    ("num_offspring", pa.int32()),
    ("cause_of_death", pa.string()),
    ("energy", pa.float32()),
    ("genotype_json", pa.string()),
])

# The map itself, every so often. Objects only: the bodies standing on it
# are the other table, so nothing is painted over and lost.
WORLD_GRID = pa.schema([
    ("step", pa.int64()),
    ("session", pa.int16()),
    ("wall_clock", pa.float64()),
    ("size", pa.int16()),
    ("grid", pa.list_(pa.int8())),
])

WORLD_AGENTS = pa.schema([
    ("step", pa.int64()),
    ("session", pa.int16()),
    ("agent_id", pa.string()),
    ("x", pa.int16()),
    ("y", pa.int16()),
])


def births(gene_names):
    """
    The births schema for THIS run's gene set.

    A phenotype has one column per gene, so the schema depends on the
    genome the run was configured with - which is also why the gene set
    goes into run.json: a log is only readable next to the genes it was
    written with.
    """
    return pa.schema(
        BIRTHS_HEAD
        + [(f"phen_{gene}", pa.float32()) for gene in sorted(gene_names)]
    )
