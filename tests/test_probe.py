import copy
import math
import os

import pytest

from src import run as runner
from src.Genome.types import reuse
from src.persistence.checkpoint_store import CheckpointStore
from src.persistence.log_reader import RunLogReader
from src.probe.runner import PROBE_DIR, run_probes, snapshots_of
from src.probe.snapshot import ProbeRecorder

EPISODE_LENGTH = 10
EPISODES = 8
PROBE_EPISODES = 3

# A run small enough for a test, with adults after five ticks.
SMALL = [
    "world.size=16",
    f"run.episode_length={EPISODE_LENGTH}",
    "life.max_childhood_steps=5",
    "checkpoints.every_steps=0",
    "probe.agents=2",
    "probe.rescue_episodes=1",
    f"probe.episodes={PROBE_EPISODES}",
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


def run_world(folder, every):
    os.makedirs(folder, exist_ok=True)
    os.chdir(folder)

    runner.main(
        episodes=EPISODES, seed=7, agent_count=4, species="clons", resume="",
        pin=False, label="t", live_every=0, probe=False,
        overrides=SMALL + [f"probe.every_episodes={every}"],
    )

    [world] = RunLogReader.find(os.path.join(folder, "logs"))
    return world


def fingerprints(world):
    return world.episode_population().column("fingerprint").to_pylist()


def steps(world):
    """
    Every step as the run took it. The agent id carries the run id, which
    is new on every launch, so an agent is named by its index here.
    """
    table = world.steps()
    columns = ["step", "x", "y", "action", "env_reward", "shaped_reward", "energy"]

    return [
        (agent_id.rsplit("-", 1)[1], *row)
        for agent_id, *row in zip(
            table.column("agent_id").to_pylist(),
            *(table.column(name).to_pylist() for name in columns),
        )
    ]


def test_snapshots_do_not_move_the_run(workdir):
    without = run_world(workdir / "off", every=0)
    with_probe = run_world(workdir / "on", every=2)

    assert snapshots_of(without.path) == []
    assert len(snapshots_of(with_probe.path)) > 0
    assert steps(with_probe) == steps(without)
    assert fingerprints(with_probe) == fingerprints(without)



def test_a_snapshot_holds_distinct_adults_on_the_grid(workdir):
    world = run_world(workdir, every=2)

    for path in snapshots_of(world.path):
        record = CheckpointStore.load(path)
        ids = [entry["agent_id"] for entry in record["agents"]]

        assert record["episode"] % 2 == 0
        assert record["step"] == record["episode"] * EPISODE_LENGTH
        assert 1 <= len(ids) <= 2
        assert len(set(ids)) == len(ids)

        for entry in record["agents"]:
            assert {"policy_net", "phenotype", "genotype", "epsilon",
                    "curiosity_beta"} <= set(entry)


def test_a_probe_world_is_a_normal_log_of_fixed_length(workdir):
    world = run_world(workdir, every=4)
    written = run_probes(world.path)

    assert written

    for folder in written:
        probe = RunLogReader(folder)
        steps = probe.steps()

        assert probe.header["probe"]["world_id"] == world.world_id
        assert steps.num_rows == PROBE_EPISODES * EPISODE_LENGTH
        assert set(steps.column("agent_id").to_pylist()) == {
            probe.header["probe"]["agent_id"]
        }
        assert all(math.isnan(energy) for energy in steps.column("energy").to_pylist())
        assert probe.episode_population().num_rows == PROBE_EPISODES
        assert probe.count("deaths") == 0
        assert probe.count("updates") == 0

    # Run again: everything on disk is skipped, nothing is written twice.
    assert run_probes(world.path) == []


def test_a_probe_world_is_reproducible(workdir):
    world = run_world(workdir, every=4)
    first = run_probes(world.path)[0]
    before = fingerprints(RunLogReader(first))

    renamed = first + "_first"
    os.rename(first, renamed)
    again = [folder for folder in run_probes(world.path) if folder == first]

    assert again == [first]
    assert fingerprints(RunLogReader(first)) == before
    assert os.path.isdir(os.path.join(world.path, PROBE_DIR))


# -----------------------------
# RESCUE
# -----------------------------
class Body:
    def __init__(self, adult):
        self.adult = adult

    def is_child(self):
        return not self.adult


class Crowd:
    def __init__(self, adults, children=0):
        self.agents = [Body(True) for _ in range(adults)] + [
            Body(False) for _ in range(children)
        ]


def recorder(rescue=1):
    from src.utils.rng import RunRandom

    made = ProbeRecorder(directory=None, every=4, count=3, rescue=rescue,
                         rng=RunRandom(1).python("probe"))
    made.written = []
    made._write = lambda chosen, episode, *rest: made.written.append(
        (episode, len(chosen))
    ) or episode

    return made


def window(made, episode, env):
    return made.end_episode(episode, episode * 10, env, None, None, None)


def test_enough_adults_are_taken_on_the_grid_and_only_there():
    made = recorder()

    for episode in range(1, 9):
        window(made, episode, Crowd(adults=5, children=2))

    assert made.written == [(4, 3), (8, 3)]


def test_too_few_adults_wait_once_then_everybody_is_taken():
    made = recorder()

    window(made, 4, Crowd(adults=1))
    assert made.written == []

    window(made, 5, Crowd(adults=2))
    assert made.written == [(5, 2)]

    # The grid does not move because of the rescue.
    window(made, 8, Crowd(adults=3))
    assert made.written == [(5, 2), (8, 3)]


def test_nobody_after_the_rescue_means_no_snapshot():
    made = recorder()

    window(made, 4, Crowd(adults=0, children=3))
    window(made, 5, Crowd(adults=0, children=3))

    assert made.written == []
    assert made.pending is None


def test_snapshots_off_build_nothing():
    from src.utils.rng import RunRandom

    assert ProbeRecorder.from_config({"probe": {"every_episodes": 0}}, None,
                                     RunRandom(1)) is None


def test_snapshots_on_without_their_numbers_are_refused():
    from src.utils.rng import RunRandom

    with pytest.raises(ValueError):
        ProbeRecorder.from_config({"probe": {"every_episodes": 2}}, None,
                                  RunRandom(1))
