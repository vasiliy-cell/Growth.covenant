import copy
import os

import pytest

from src import run as runner
from src.Genome.types import reuse
from src.persistence.checkpoint_store import CheckpointStore
from src.persistence.log_reader import RunLogReader
from src.persistence.run_log import RunLog

SMALL = [
    "world.size=16",
    "run.episode_length=10",
    "life.max_childhood_steps=5",
    "checkpoints.every_steps=0",
    "probe.every_episodes=0",
]


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """
    Runs in a folder of its own, and leaves the world's module-level
    config the way it found it: the runner's --set lands there too.
    """
    saved = copy.deepcopy(reuse.config)
    monkeypatch.chdir(tmp_path)

    yield tmp_path

    reuse.config.clear()
    reuse.config.update(saved)


def run_world(folder, episodes, resume=""):
    os.makedirs(folder, exist_ok=True)
    os.chdir(folder)

    runner.main(
        episodes=episodes, seed=7, agent_count=4, species="clons",
        resume=resume, pin=False, label="t", live_every=0, probe=False,
        overrides=SMALL,
    )

    [world] = RunLogReader.find(os.path.join(folder, "logs"))
    return world


def fingerprints(world):
    return world.episode_population().column("fingerprint").to_pylist()


def test_two_launches_of_one_seed_print_the_same_fingerprints(workdir):
    first = run_world(workdir / "first", episodes=6)
    second = run_world(workdir / "second", episodes=6)

    assert first.world_id != second.world_id
    assert fingerprints(first) == fingerprints(second)


def test_a_resumed_world_goes_on_with_the_same_chain(workdir):
    whole = run_world(workdir / "whole", episodes=6)

    run_world(workdir / "halves", episodes=3)
    [saved] = CheckpointStore(str(workdir / "halves" / "checkpoints")).list()
    halves = run_world(workdir / "halves", episodes=3, resume=saved["path"])

    assert len(halves.sessions) == 2
    assert fingerprints(halves) == fingerprints(whole)


def make_log(path):
    return RunLog(
        directory=str(path), world_id="world-1", run_id="run-1", seed=1,
        episode_length=2, config={}, species="clons", gene_names=[],
    )


def log_steps(log, steps):
    for step in steps:
        log.log_step(
            step=step, agent_id="world-1-0000", position=(step, 0), action=1,
            env_reward=0.0, intrinsic_reward=0.0, shaped_reward=0.0,
            energy=1.0, age=step,
        )


def test_the_chain_survives_being_written_down(tmp_path):
    whole = make_log(tmp_path / "whole")
    log_steps(whole, range(1, 7))

    first = make_log(tmp_path / "split")
    log_steps(first, range(1, 4))
    saved = first.fingerprint

    second = make_log(tmp_path / "split")
    second.fingerprint = saved
    log_steps(second, range(4, 7))

    assert second.fingerprint == whole.fingerprint
    assert len(whole.fingerprint) == 16


def test_no_saved_chain_starts_a_new_one(tmp_path):
    fresh = make_log(tmp_path / "fresh")
    reset = make_log(tmp_path / "reset")
    reset.fingerprint = None

    log_steps(fresh, range(1, 4))
    log_steps(reset, range(1, 4))

    assert reset.fingerprint == fresh.fingerprint
