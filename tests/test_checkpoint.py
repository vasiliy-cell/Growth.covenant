import importlib.util
import io
import os
import shutil

import pytest
import torch

from src.Agent.life import Life
from src.Brain.BrainManager import BrainManager
from src.environment.env import GridWorldEnv
from src.persistence.checkpoint import SCHEMA_VERSION, Checkpoint
from src.persistence.checkpoint_store import CheckpointStore
from src.run import encode_observation
from src.utils.rng import RunRandom

OBS_SIZE = 2 + 7 * 7


def make_run(seed=1, size=10, agents=2, species="clons"):
    """A whole run in miniature: a world, its minds and its streams."""
    rng = RunRandom(seed)

    env = GridWorldEnv(
        size=size,
        rng=rng,
        agent_count=agents,
        species_name=species,
        life=Life(childhood_steps=10 ** 9, start_energy=100.0),
    )
    observations = env.start()

    brains = make_brains(env, rng)

    return env, brains, rng, observations


def make_brains(env, rng):
    return BrainManager(
        config={},
        obs_size=OBS_SIZE,
        action_size=len(env.get_action_space()),
        rng=rng,
    )


def tick(env, brains, observations):
    """One step of the runner's loop, learning included."""
    phenotypes = {
        agent_id: env.make_phenotype(agent_id)
        for agent_id in env.agents.ids()
        if agent_id not in brains
    }
    brains.sync(env.agents, phenotypes)

    for brain in brains:
        # A test cannot wait 500 ticks of warmup for the optimiser, the
        # target net and the replay stream to start mattering.
        brain.min_buffer_size = 2
        brain.batch_size = 2

    available = env.get_available_actions()
    states = {
        agent_id: encode_observation(observation)
        for agent_id, observation in observations.items()
    }
    actions = {
        agent_id: brains.get(agent_id).choose_action(state, available[agent_id])
        for agent_id, state in states.items()
    }

    next_observations, rewards, _ = env.step(actions)

    for agent_id in actions:
        if agent_id not in next_observations:
            continue

        brain = brains.get(agent_id)
        shaped, _ = brain.shape_reward(next_observations[agent_id], rewards[agent_id])
        brain.remember(
            states[agent_id],
            actions[agent_id],
            shaped,
            encode_observation(next_observations[agent_id]),
            False,
        )
        brain.learn()

    return next_observations, actions


def run_for(env, brains, observations, steps):
    trace = []

    for _ in range(steps):
        observations, actions = tick(env, brains, observations)
        trace.append((dict(actions), env.agents.positions()))

    return observations, trace


def through_disk(record):
    """
    The record as a fresh process reads it back: serialized and loaded.

    capture() hands out the live tensors of the run it describes - weights,
    Adam moments, replay - and the store writes them to disk at once, so a
    real resume only ever sees a copy taken at that moment. Restoring from
    the object in memory would give the "resumed" minds the very tensors
    the original keeps training - moved on by then, and sharing one Adam.
    """
    buffer = io.BytesIO()
    torch.save(record, buffer)
    buffer.seek(0)

    return torch.load(buffer, weights_only=False)


def capture(env, brains, rng, step=0, with_replay=True):
    return through_disk(Checkpoint.capture(
        env,
        brains,
        rng,
        run={"run_id": "run-test", "world_id": "world-test", "seed": 1, "step": step},
        config={"world": {"size": 10}},
        with_replay=with_replay,
    ))


def resume(record, seed=999, species="clons"):
    """A fresh process would look exactly like this: build, then restore."""
    rng = RunRandom(seed)

    env = GridWorldEnv(
        size=record["env"]["world"]["size"],
        rng=rng,
        agent_count=1,
        species_name=species,
        life=Life(childhood_steps=10 ** 9, start_energy=100.0),
    )

    _, observations, brains = Checkpoint.restore(
        record, env, lambda obs: make_brains(env, rng), rng
    )

    return env, brains, rng, observations


# -----------------------------
# THE WHOLE POINT
# -----------------------------
def test_a_resumed_run_takes_exactly_the_same_next_steps():
    """
    Not "it starts up again" - the same actions, in the same places, on
    the same map. Anything less and a checkpoint is a new experiment
    wearing an old run's name.
    """
    env, brains, rng, observations = make_run()
    observations, _ = run_for(env, brains, observations, 12)

    record = capture(env, brains, rng, step=12)

    _, expected = run_for(env, brains, observations, 8)

    twin_env, twin_brains, _, twin_observations = resume(record)
    _, resumed = run_for(twin_env, twin_brains, twin_observations, 8)

    assert resumed == expected


def test_a_resumed_world_is_the_world_that_was_saved():
    env, brains, rng, observations = make_run()
    run_for(env, brains, observations, 10)

    resumed_env = resume(capture(env, brains, rng, step=10))[0]

    assert (resumed_env.world.map.grid == env.world.map.grid).all()
    assert resumed_env.current_step == env.current_step
    assert resumed_env.agents.positions() == env.agents.positions()
    assert [a.energy for a in resumed_env.agents] == [a.energy for a in env.agents]
    assert [a.age for a in resumed_env.agents] == [a.age for a in env.agents]


def test_a_resumed_mind_is_the_mind_that_was_saved():
    env, brains, rng, observations = make_run()
    run_for(env, brains, observations, 10)

    resumed_brains = resume(capture(env, brains, rng, step=10))[1]

    for agent_id, brain in brains.items():
        twin = resumed_brains.get(agent_id)

        saved = brain.trainer.state()
        loaded = twin.trainer.state()

        for key in saved["policy_net"]:
            assert torch.equal(saved["policy_net"][key], loaded["policy_net"][key])
            assert torch.equal(saved["target_net"][key], loaded["target_net"][key])

        assert loaded["training_step"] == saved["training_step"]
        assert twin.policy.epsilon == brain.policy.epsilon
        assert twin.age == brain.age
        assert (
            twin.reward_shaping.curiosity.visit_counts
            == brain.reward_shaping.curiosity.visit_counts
        )
        assert len(twin.replay_buffer) == len(brain.replay_buffer)


def test_a_light_checkpoint_leaves_the_memories_behind():
    """The heavy half is optional on purpose - and must still restore."""
    env, brains, rng, observations = make_run()
    run_for(env, brains, observations, 10)

    record = capture(env, brains, rng, step=10, with_replay=False)

    assert record["has_replay"] is False

    resumed_brains = resume(record)[1]

    assert all(len(brain.replay_buffer) == 0 for brain in resumed_brains)


# -----------------------------
# REFUSALS
# -----------------------------
def test_a_checkpoint_of_another_species_is_refused():
    """A genotype only means something to the species that wrote it."""
    env, brains, rng, observations = make_run(species="clons")
    run_for(env, brains, observations, 3)

    with pytest.raises(ValueError, match="species"):
        resume(capture(env, brains, rng), species="non_linear")


def test_a_checkpoint_of_another_schema_is_refused():
    env, brains, rng, observations = make_run()
    record = capture(env, brains, rng)
    record["schema_version"] = SCHEMA_VERSION + 1

    with pytest.raises(ValueError, match="schema"):
        resume(record)


def test_config_drift_is_reported_section_by_section():
    env, brains, rng, _ = make_run()
    record = capture(env, brains, rng)

    assert Checkpoint.config_drift(record, {"world": {"size": 10}}) == []
    assert Checkpoint.config_drift(record, {"world": {"size": 64}}) == ["world"]


# -----------------------------
# THE STORE
# -----------------------------
def test_only_the_newest_rolling_checkpoints_survive(tmp_path):
    store = CheckpointStore(directory=str(tmp_path), keep=3)

    for step in range(1, 7):
        store.save({"step": step}, run_id="run", step=step)

    assert [c["step"] for c in store.list(pinned=False)] == [6, 5, 4]


def test_a_pinned_checkpoint_outlives_every_rotation(tmp_path):
    store = CheckpointStore(directory=str(tmp_path), keep=2)

    store.save({"step": 1}, run_id="run", step=1)
    store.pin("run_step000000001.pt")

    for step in range(2, 9):
        store.save({"step": step}, run_id="run", step=step)

    assert [c["step"] for c in store.list(pinned=True)] == [1]
    assert len(store.list(pinned=False)) == 2


def test_pinning_never_costs_the_rolling_pool_a_slot(tmp_path):
    """
    Four kept runs must not mean one rolling checkpoint instead of five.
    The two folders are counted separately, and only rolling/ is pruned.
    """
    store = CheckpointStore(directory=str(tmp_path), keep=5)

    for step in range(1, 5):
        store.save({"step": step}, run_id="keeper", step=step, pinned=True)

    for step in range(10, 20):
        store.save({"step": step}, run_id="run", step=step)

    assert len(store.list(pinned=False)) == 5
    assert len(store.list(pinned=True)) == 4


def test_a_file_moved_into_the_pinned_folder_by_hand_is_pinned(tmp_path):
    """
    What a file manager does is the whole mechanism - there is no index
    anywhere that a drag and drop could get out of step with.
    """
    store = CheckpointStore(directory=str(tmp_path), keep=1)
    path = store.save({"step": 1}, run_id="run", step=1)

    shutil.move(path, os.path.join(store.pinned_directory, os.path.basename(path)))

    for step in range(2, 6):
        store.save({"step": step}, run_id="run", step=step)

    pinned = store.list(pinned=True)

    assert [c["step"] for c in pinned] == [1]
    assert os.path.isfile(pinned[0]["path"])


def test_both_folders_exist_before_anything_is_written(tmp_path):
    """A folder you cannot see is a folder you will not drag a file into."""
    store = CheckpointStore(directory=str(tmp_path), keep=5)
    store.prepare()

    assert os.path.isdir(store.rolling_directory)
    assert os.path.isdir(store.pinned_directory)


def test_checkpoints_from_before_the_folder_split_are_still_found(tmp_path):
    """Nobody loses a run to a refactor."""
    store = CheckpointStore(directory=str(tmp_path), keep=5)
    legacy = os.path.join(str(tmp_path), "old_step000000007.pt")
    CheckpointStore._write({"step": 7}, legacy)

    found = store.list(pinned=False)

    assert [c["step"] for c in found] == [7]
    assert store.pin("old_step000000007.pt").endswith(
        os.path.join("pinned", "old_step000000007.pt")
    )


def test_unpinning_puts_it_back_in_reach_of_the_rotation(tmp_path):
    store = CheckpointStore(directory=str(tmp_path), keep=1)

    store.save({"step": 1}, run_id="run", step=1, pinned=True)
    store.unpin("run_step000000001.pt")

    assert store.list(pinned=True) == []
    assert [c["step"] for c in store.list(pinned=False)] == [1]


def load_cli():
    """scripts/ is not a package, so the tool is loaded by path."""
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts",
        "checkpoints.py",
    )
    spec = importlib.util.spec_from_file_location("checkpoints_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def filled_store(tmp_path):
    store = CheckpointStore(directory=str(tmp_path), keep=10)

    for run_id, step in (("alpha", 1), ("beta", 2), ("beta", 3)):
        store.save({"step": step}, run_id=run_id, step=step)

    return store


def test_a_checkpoint_can_be_picked_by_its_number_or_by_name(tmp_path):
    cli = load_cli()
    store = filled_store(tmp_path)

    listing = store.list()

    assert cli.find(store, "1")["name"] == listing[0]["name"]
    assert cli.find(store, "latest")["name"] == listing[0]["name"]
    assert cli.find(store, "alpha")["run_id"] == "alpha"
    assert cli.find(store, listing[2]["name"])["name"] == listing[2]["name"]


def test_an_ambiguous_name_is_an_error_and_not_a_guess(tmp_path):
    """These files are the only copy of a run - never pin by coin toss."""
    cli = load_cli()
    store = filled_store(tmp_path)

    with pytest.raises(SystemExit, match="several"):
        cli.find(store, "beta")

    with pytest.raises(SystemExit, match="Nothing matches"):
        cli.find(store, "gamma")


def test_a_save_leaves_no_half_written_file_behind(tmp_path):
    """The rename is atomic, so nothing ever sees a partial checkpoint."""
    store = CheckpointStore(directory=str(tmp_path), keep=5)
    path = store.save({"step": 1}, run_id="run", step=1)

    assert os.path.isfile(path)
    assert not any(name.endswith(".writing") for name in os.listdir(str(tmp_path)))
    assert CheckpointStore.load(path) == {"step": 1}
