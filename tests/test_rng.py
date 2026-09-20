import os
import subprocess
import sys

import torch

from src.utils.rng import RunRandom


def draws(rng, count=5):
    """A little of everything, so a test compares whole streams at once."""
    return (
        [rng.python("world").random() for _ in range(count)],
        [float(rng.numpy("genome").normal()) for _ in range(count)],
        [
            torch.rand(1, generator=rng.torch("agent", 1, "policy")).item()
            for _ in range(count)
        ],
    )


# -----------------------------
# THE SEED IS THE RUN
# -----------------------------
def test_the_same_seed_gives_the_same_streams():
    assert draws(RunRandom(99)) == draws(RunRandom(99))


def test_a_different_seed_gives_different_streams():
    assert draws(RunRandom(99)) != draws(RunRandom(100))


def test_a_stream_is_the_same_object_every_time_it_is_asked_for():
    """Two objects for one name would replay the same numbers twice."""
    rng = RunRandom(1)

    assert rng.python("world") is rng.python("world")
    assert rng.numpy("genome") is rng.numpy("genome")


# -----------------------------
# INDEPENDENCE
# -----------------------------
def test_two_names_are_two_streams():
    rng = RunRandom(1)

    world = [rng.python("world").random() for _ in range(5)]
    population = [rng.python("population").random() for _ in range(5)]

    assert world != population


def test_the_kind_is_part_of_the_name():
    """numpy("world") must not be python("world") drawing the same numbers."""
    rng = RunRandom(1)

    assert rng.seed_for("world") != rng.seed_for("population")
    assert [rng.python("x").random() for _ in range(3)] != [
        float(value) for value in rng.numpy("x").random(3)
    ]


def test_draining_one_stream_leaves_the_others_where_they_were():
    """
    The reason named streams exist: a tick with one more fight in it, or
    one more birth, must not move the map or anybody's mind.
    """
    quiet = RunRandom(5)
    busy = RunRandom(5)

    for _ in range(1000):
        busy.python("movement").random()

    assert quiet.python("world").random() == busy.python("world").random()
    assert quiet.seed_for("agent", 3, "brain") == busy.seed_for("agent", 3, "brain")


def test_an_agent_stream_does_not_depend_on_how_many_agents_there_are():
    alone = RunRandom(5)
    crowded = RunRandom(5)

    for index in range(50):
        crowded.seed_for("agent", index, "brain")

    assert alone.seed_for("agent", 7, "brain") == crowded.seed_for("agent", 7, "brain")


# -----------------------------
# ACROSS PROCESSES
# -----------------------------
def test_a_name_means_the_same_in_a_fresh_process():
    """
    Names are hashed with crc32 and not with hash(), which python salts per
    process - the same run launched twice has to be the same run.
    """
    rng = RunRandom(77)
    here = rng.python("world").random()

    environment = dict(os.environ, PYTHONHASHSEED="12345", PYTHONPATH=os.getcwd())
    there = subprocess.check_output(
        [
            sys.executable,
            "-c",
            "from src.utils.rng import RunRandom;"
            "print(repr(RunRandom(77).python('world').random()))",
        ],
        env=environment,
    )

    assert float(there) == here


# -----------------------------
# SNAPSHOT / RESUME
# -----------------------------
def test_a_snapshot_puts_every_stream_back():
    rng = RunRandom(3)
    draws(rng)

    snapshot = rng.state()
    expected = draws(rng)

    rng.load_state(snapshot)

    assert draws(rng) == expected


def test_a_snapshot_restores_the_stream_objects_already_handed_out():
    """
    A policy holds its generator and a buffer its sampler long before a
    run is restored. Handing back fresh objects would restore streams
    nobody draws from, and every mind would carry on unrestored.
    """
    rng = RunRandom(3)
    held = rng.python("agent", 2, "replay")

    snapshot = rng.state()
    expected = held.random()

    held.random()
    rng.load_state(snapshot)

    assert rng.python("agent", 2, "replay") is held
    assert held.random() == expected


def test_a_snapshot_resumes_a_run_in_a_fresh_object():
    """What a checkpoint needs: continue the run, do not restart it."""
    rng = RunRandom(3)
    draws(rng)

    snapshot = rng.state()
    expected = draws(rng)

    resumed = RunRandom(0)
    resumed.load_state(snapshot)

    assert draws(resumed) == expected
