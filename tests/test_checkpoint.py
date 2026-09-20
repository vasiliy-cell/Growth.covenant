import os

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


def capture(env, brains, rng, step=0, with_replay=True):
    return Checkpoint.capture(
        env,
        brains,
        rng,
        run={"run_id": "run-test", "world_id": "world-test", "seed": 1, "step": step},
        config={"world": {"size": 10}},
        with_replay=with_replay,
    )


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


def test_unpinning_puts_it_back_in_reach_of_the_rotation(tmp_path):
    store = CheckpointStore(directory=str(tmp_path), keep=1)

    store.save({"step": 1}, run_id="run", step=1, pinned=True)
    store.unpin("run_step000000001.pt")

    assert store.list(pinned=True) == []
    assert [c["step"] for c in store.list(pinned=False)] == [1]


def test_a_save_leaves_no_half_written_file_behind(tmp_path):
    """The rename is atomic, so nothing ever sees a partial checkpoint."""
    store = CheckpointStore(directory=str(tmp_path), keep=5)
    path = store.save({"step": 1}, run_id="run", step=1)

    assert os.path.isfile(path)
    assert not any(name.endswith(".writing") for name in os.listdir(str(tmp_path)))
    assert CheckpointStore.load(path) == {"step": 1}
