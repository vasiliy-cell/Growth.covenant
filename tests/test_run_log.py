import base64
import json
import os

import numpy as np

from src.persistence.log_reader import RunLogReader
from src.persistence.run_log import RunLog
from src.utils.rng import RunRandom

GENES = ["alpha", "gamma", "learning_rate"]
CONFIG = {"world": {"size": 8}, "run": {"episode_length": 4}}


def make_log(tmp_path, world_id="world-1", label=None, max_rows=1000, **extra):
    return RunLog(
        directory=str(tmp_path),
        world_id=world_id,
        run_id=extra.pop("run_id", "run-1"),
        seed=42,
        episode_length=4,
        config=CONFIG,
        species="clons",
        gene_names=GENES,
        label=label,
        max_rows=max_rows,
        **extra,
    )


def phenotype(value=1.0):
    return {gene: value for gene in GENES}


def write_episodes(log, episodes=10, agents=2, steps_per_episode=4, start=0):
    """A miniature run: steps, updates, a birth, a death, snapshots."""
    step = start
    ids = [f"agent-{index}" for index in range(agents)]

    for episode in range(episodes):
        for _ in range(steps_per_episode):
            step += 1

            for index, agent_id in enumerate(ids):
                log.log_step(
                    step=step,
                    agent_id=agent_id,
                    position=(index, step % 8),
                    action=index % 8,
                    env_reward=5.0,
                    intrinsic_reward=0.5,
                    shaped_reward=5.5,
                    energy=100.0 - step,
                    age=step,
                )
                log.log_update(
                    step=step,
                    agent_id=agent_id,
                    training_step=step,
                    metrics={
                        "loss": 2.0,
                        "grad_norm": 1.0,
                        "td_error": -0.5,
                        "target_q": 3.0,
                        "q_prediction": 2.5,
                    },
                    curiosity_beta=4.0,
                    epsilon=0.7,
                    buffer_size=step,
                )

            if log.should_snapshot(step):
                log.log_world(
                    step=step,
                    grid=np.zeros((8, 8), dtype=np.int8),
                    positions={agent_id: (1, 2) for agent_id in ids},
                )

        log.end_episode(
            step=step,
            agents={
                agent_id: {
                    "epsilon": 0.7,
                    "curiosity_beta": 4.0,
                    "energy": 50.0,
                    "age": step,
                }
                for agent_id in ids
            },
            non_empty_ratio=0.2,
        )

    return step, ids


# -----------------------------
# WRITE IT, THEN READ IT
# -----------------------------
def test_ten_episodes_come_back_exactly_as_they_went_in(tmp_path):
    """
    The rule of this format: if you cannot load what you wrote, you did
    not write it.
    """
    log = make_log(tmp_path, world_snapshot_every=4)
    step, ids = write_episodes(log, episodes=10)
    log.close()

    reader = RunLogReader(log.path)

    assert reader.episode_population().num_rows == 10
    assert reader.episode_agents().num_rows == 10 * len(ids)
    assert reader.steps().num_rows == 10 * 4 * len(ids)
    assert reader.updates().num_rows == 10 * 4 * len(ids)

    steps = reader.steps()
    assert steps["step"].to_pylist()[-1] == step
    assert set(steps["agent_id"].to_pylist()) == set(ids)
    assert steps["env_reward"][0].as_py() == 5.0

    summary = reader.episode_population()
    assert summary["steps"].to_pylist() == [4 * len(ids)] * 10
    assert summary["env_reward"][0].as_py() == 4 * len(ids) * 5.0
    assert summary["episode"].to_pylist() == list(range(10))


def test_a_crash_costs_only_what_was_still_in_memory(tmp_path):
    """
    No close(), no flush of the last window - exactly what a kill -9
    leaves behind. Everything already written must still read.
    """
    log = make_log(tmp_path, max_rows=8)
    write_episodes(log, episodes=10)

    reader = RunLogReader(log.path)

    assert reader.steps().num_rows >= 8
    assert reader.episode_population().num_rows >= 1


def test_floats_are_float32_and_sums_are_float64(tmp_path):
    """Four bytes where three digits are meant, eight where it adds up."""
    log = make_log(tmp_path)
    write_episodes(log, episodes=2)
    log.close()

    reader = RunLogReader(log.path)

    assert reader.steps().schema.field("env_reward").type == "float"
    assert reader.updates().schema.field("loss").type == "float"
    assert reader.episode_population().schema.field("env_reward").type == "double"
    assert reader.steps().schema.field("wall_clock").type == "double"


# -----------------------------
# LIFE AND DEATH
# -----------------------------
def test_a_birth_keeps_the_genotype_whole_and_the_phenotype_in_columns(tmp_path):
    log = make_log(tmp_path)

    log.log_birth(
        step=7,
        agent_id="child",
        index=3,
        parents=["mother", "father"],
        energy=100.0,
        genotype={"gamma": [[0.9, "A"], [0.8, "a"]]},
        phenotype=phenotype(0.5),
    )
    log.close()

    births = RunLogReader(log.path).births()

    assert births.num_rows == 1
    assert births["parents"][0].as_py() == ["mother", "father"]
    assert births["phen_gamma"][0].as_py() == 0.5
    assert json.loads(births["genotype_json"][0].as_py()) == {
        "gamma": [[0.9, "A"], [0.8, "a"]]
    }


def test_a_death_is_one_row_with_the_whole_life_in_it(tmp_path):
    log = make_log(tmp_path)

    log.log_death(step=90, record={
        "agent_id": "elder",
        "index": 1,
        "parents": ["mother"],
        "birth_step": 10,
        "death_step": 90,
        "lifespan": 80,
        "cumulative_reward": 125.5,
        "num_offspring": 3,
        "cause_of_death": "starvation",
        "energy": -0.5,
        "genotype": {"gamma": 0.99},
    })
    log.close()

    death = RunLogReader(log.path).deaths().to_pylist()[0]

    assert death["agent_id"] == "elder"
    assert death["lifespan"] == 80
    assert death["num_offspring"] == 3
    assert death["cause_of_death"] == "starvation"
    assert death["cumulative_reward"] == 125.5


# -----------------------------
# THE MAP
# -----------------------------
def test_a_snapshot_keeps_the_map_and_the_bodies_apart(tmp_path):
    """
    Painting the bodies into the grid would hide the cell each one stands
    on - which is the cell you opened the snapshot to look at.
    """
    log = make_log(tmp_path, world_snapshot_every=2)

    grid = np.arange(64, dtype=np.int8).reshape(8, 8) % 3
    log.log_world(step=10, grid=grid, positions={"a": (1, 2), "b": (3, 4)})
    log.close()

    reader = RunLogReader(log.path)

    assert np.array_equal(reader.grid_at(10), grid)
    assert reader.world_agents().num_rows == 2
    assert reader.world_agents()["x"].to_pylist() == [1, 3]


# -----------------------------
# ONE WORLD, MANY CONTINUATIONS
# -----------------------------
def test_a_continued_world_writes_into_the_same_folder(tmp_path):
    first = make_log(tmp_path, run_id="run-1")
    step, _ = write_episodes(first, episodes=3)
    first.close()

    second = RunLog(
        directory=str(tmp_path),
        world_id="world-1",
        run_id="run-2",
        seed=42,
        episode_length=4,
        config=CONFIG,
        species="clons",
        gene_names=GENES,
        resumed_from="checkpoints/rolling/run-1_step000000012.pt",
    )
    second.episode = 3
    write_episodes(second, episodes=2, start=step)
    second.close()

    assert first.path == second.path

    reader = RunLogReader(second.path)
    sessions = reader.sessions

    assert len(sessions) == 2
    assert sessions[0]["from_step"] == 1
    assert sessions[1]["from_step"] == step + 1
    assert sessions[1]["resumed_from"].endswith(".pt")
    assert reader.episode_population().num_rows == 5
    assert set(reader.steps()["session"].to_pylist()) == {0, 1}


def test_a_series_nests_the_folder_and_the_reader_still_finds_it(tmp_path):
    """A series is a folder and a word in run.json, not a new concept."""
    log = make_log(tmp_path, label="third try", series="leak sweep")
    write_episodes(log, episodes=1)
    log.close()

    assert os.path.basename(os.path.dirname(log.path)) == "leak-sweep"

    found = RunLogReader.find(str(tmp_path))

    assert [reader.path for reader in found] == [log.path]
    assert found[0].series == "leak sweep"


def test_the_live_file_says_what_is_happening_right_now(tmp_path):
    """
    A few kilobytes for whoever is watching, and nothing at all for the
    simulation to know about them.
    """
    log = make_log(tmp_path, live_every=5, live_dir=str(tmp_path / ".panel" / "live"))
    grid = np.arange(64, dtype=np.int8).reshape(8, 8) % 3

    assert log.should_live(5)
    assert not log.should_live(4)

    log.log_live(
        step=5,
        grid=grid,
        positions={"a": (1, 2)},
        agents=1,
        reward=12.5,
        epsilon=0.6,
    )

    with open(log.live_path, encoding="utf-8") as handle:
        live = json.load(handle)

    assert os.path.dirname(log.live_path) == str(tmp_path / ".panel" / "live")
    assert live["step"] == 5
    assert live["agents"] == 1
    assert live["positions"] == [["a", 1, 2]]
    assert np.array_equal(
        np.frombuffer(base64.b64decode(live["grid"]), dtype=np.int8).reshape(8, 8),
        grid,
    )


def test_the_label_names_the_folder_and_the_id_finds_it(tmp_path):
    log = make_log(tmp_path, label="mendel long childhood")

    assert os.path.basename(log.path) == "world-1_mendel-long-childhood"
    assert RunLog.folder_for(str(tmp_path), "world-1") == log.path


# -----------------------------
# HEADER AND RNG
# -----------------------------
def test_the_header_says_how_to_repeat_the_run(tmp_path):
    log = make_log(tmp_path)
    log.close()

    header = RunLogReader(log.path).header

    assert header["schema_version"] == 1
    assert header["species"] == "clons"
    assert header["genes"] == sorted(GENES)
    assert header["episode_length"] == 4
    assert header["config"] == CONFIG
    assert header["sessions"][0]["seed"] == 42
    assert header["versions"]["pyarrow"]
    assert header["commit"] is None or len(header["commit"]) == 40


def test_the_world_streams_are_snapshotted_more_often_than_the_agents(tmp_path):
    """
    Fifty agents every window would be gigabytes of random bytes that do
    not compress - and the checkpoints carry every stream anyway.
    """
    log = make_log(tmp_path, rng_world_every=1, rng_agents_every=5)
    rng = RunRandom(42)

    rng.python("world").random()
    rng.torch("agent", 0, "policy")

    for episode in range(10):
        log.log_rng(rng, step=episode * 4)
        log.episode += 1

    log.close()

    reader = RunLogReader(log.path)

    assert len(reader.rng("world")) == 10
    assert len(reader.rng("agents")) == 2
    assert "python:world" in reader.rng("world")[0]["streams"]
    assert "torch:agent/0/policy" in reader.rng("agents")[0]["streams"]
