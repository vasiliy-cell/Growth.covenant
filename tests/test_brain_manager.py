import random

import torch

from src.Agent.AgentManager import AgentManager
from src.Brain.BrainManager import BrainManager
from src.persistence.checkpoint_writer import CheckpointWriter
from src.utils.rng import RunRandom
from src.world.world import World

# One read genotype: what the runner hands to BrainManager for a newborn.
PHENOTYPE = {
    "epsilon": 1.0,
    "epsilon_decay": 0.5,
    "epsilon_min": 0.01,
    "buffer_size": 100,
    "batch_size": 4,
    "min_buffer_size": 2,
    "curiosity_beta": 4.0,
    "curiosity_decay": 0.5,
    "hidden_size": 16,
    "hidden_layers": 2,
    "gamma": 0.99,
    "learning_rate": 0.001,
    "max_norm": 0.01,
    "target_update_freq": 10000,
}


def make_population(count=3, seed=0):
    world = World(size=8)
    world.generate(rng=random.Random(seed))

    agents = AgentManager(world, rng=random.Random(seed))
    agents.spawn(count)

    return agents


def make_brains(checkpoints=None, seed=0):
    return BrainManager(
        config={},
        obs_size=51,
        action_size=8,
        checkpoints=checkpoints,
        rng=RunRandom(seed),
    )


def sync(brains, agents):
    """What the runner does: a phenotype for every body without a mind."""
    phenotypes = {
        agent_id: dict(PHENOTYPE)
        for agent_id in agents.ids()
        if agent_id not in brains
    }

    brains.sync(agents, phenotypes)


# -----------------------------
# FOLLOWING THE POPULATION
# -----------------------------
def test_every_agent_gets_a_mind():
    agents = make_population(3)
    brains = make_brains()

    sync(brains, agents)

    assert len(brains) == 3
    assert all(agent_id in brains for agent_id in agents.ids())


def test_sync_is_idempotent():
    agents = make_population(3)
    brains = make_brains()

    sync(brains, agents)
    first = brains.get(agents.ids()[0])
    sync(brains, agents)

    assert len(brains) == 3
    assert brains.get(agents.ids()[0]) is first


def test_a_newcomer_gets_its_own_mind():
    agents = make_population(2)
    brains = make_brains()
    sync(brains, agents)

    newborn = agents.spawn(1)[0]
    sync(brains, agents)

    assert len(brains) == 3
    assert newborn.agent_id in brains


def test_a_departed_agent_leaves_no_mind_behind():
    agents = make_population(3)
    brains = make_brains()
    sync(brains, agents)

    gone = agents.ids()[0]
    agents.remove(gone)
    sync(brains, agents)

    assert len(brains) == 2
    assert gone not in brains


def test_minds_are_not_shared():
    """
    The whole point of a brain per agent: two agents must never end up
    behind the same weights, buffer, epsilon or curiosity.
    """
    agents = make_population(2)
    brains = make_brains()
    sync(brains, agents)

    first, second = (brains.get(agent_id) for agent_id in agents.ids())

    assert first is not second
    assert first.trainer is not second.trainer
    assert first.replay_buffer is not second.replay_buffer
    assert first.policy is not second.policy
    assert first.reward_shaping.curiosity is not second.reward_shaping.curiosity


def test_a_full_buffer_belongs_to_one_agent_only():
    agents = make_population(2)
    brains = make_brains()
    sync(brains, agents)

    first, second = (brains.get(agent_id) for agent_id in agents.ids())
    first.remember(state="s", action=0, reward=1, next_state="s", done=False)

    assert len(first.replay_buffer) == 1
    assert len(second.replay_buffer) == 0


# -----------------------------
# REPRODUCIBILITY
# -----------------------------
def test_a_mind_is_built_from_the_seed_and_nothing_else():
    """Same seed, same weights - a run can be replayed, not just repeated."""
    first, second = make_brains(seed=4), make_brains(seed=4)
    agents = make_population(2)

    sync(first, agents)
    sync(second, agents)

    for agent_id in agents.ids():
        left = first.get(agent_id).trainer.state_dict()
        right = second.get(agent_id).trainer.state_dict()

        assert all(torch.equal(left[key], right[key]) for key in left)


def test_a_mind_belongs_to_an_index_and_not_to_a_birth_order():
    """
    Agent 2 gets the same mind whether it was born into a crowd or into an
    empty world: its weights come from its own stream, so a birth or a
    death somewhere else cannot change them.
    """
    crowd = make_population(3, seed=1)
    crowd_brains = make_brains(seed=4)
    sync(crowd_brains, crowd)

    alone = make_population(1, seed=1)
    for _ in range(2):
        alone.spawn(1)  # indexes 1 and 2, born one at a time
    alone_brains = make_brains(seed=4)
    sync(alone_brains, alone)

    third_of_a_crowd = crowd_brains.get(crowd.all()[2].agent_id)
    last_of_the_line = alone_brains.get(alone.all()[2].agent_id)

    left = third_of_a_crowd.trainer.state_dict()
    right = last_of_the_line.trainer.state_dict()

    assert all(torch.equal(left[key], right[key]) for key in left)


# -----------------------------
# PERSONAL SCHEDULES
# -----------------------------
def test_a_newborn_starts_exploring_from_scratch():
    """
    Epsilon follows the age of the individual, not the age of the run: an
    agent born among veterans has to discover the world for itself.
    """
    agents = make_population(1)
    brains = make_brains()
    sync(brains, agents)

    for _ in range(3):
        brains.next_episode()

    veteran = brains.get(agents.ids()[0])

    newborn_agent = agents.spawn(1)[0]
    sync(brains, agents)
    newborn = brains.get(newborn_agent.agent_id)

    assert veteran.policy.epsilon < newborn.policy.epsilon
    assert newborn.policy.epsilon == PHENOTYPE["epsilon"]
    assert newborn.reward_shaping.curiosity.beta == PHENOTYPE["curiosity_beta"]


def test_curiosity_is_personal():
    """A cell one agent wore out is still new to everybody else."""
    agents = make_population(2)
    brains = make_brains()
    sync(brains, agents)

    first, second = (brains.get(agent_id) for agent_id in agents.ids())

    first.shape_reward("somewhere", 0.0)
    first_again, _ = first.shape_reward("somewhere", 0.0)
    stranger, _ = second.shape_reward("somewhere", 0.0)

    assert first_again < stranger


# -----------------------------
# CHECKPOINTS
# -----------------------------
def test_a_retired_mind_is_written_down(tmp_path):
    agents = make_population(2)
    checkpoints = CheckpointWriter(models_dir=str(tmp_path), run_id="run-test")
    brains = make_brains(checkpoints)
    sync(brains, agents)

    gone = agents.ids()[0]
    brains.get(gone).remember("s", 0, 1, "s", False)

    agents.remove(gone)
    sync(brains, agents)

    record = torch.load(checkpoints.path_for(gone), weights_only=False)

    assert record["agent_id"] == gone
    assert record["run_id"] == "run-test"
    assert record["age"] == 1
    assert record["epsilon"] == PHENOTYPE["epsilon"]
    assert "policy_net" in record


def test_the_whole_population_is_written_down(tmp_path):
    agents = make_population(3)
    checkpoints = CheckpointWriter(models_dir=str(tmp_path), run_id="run-test")
    brains = make_brains(checkpoints)
    sync(brains, agents)

    saved = checkpoints.save_all(brains)

    assert len(saved) == 3
    assert {path.name for path in tmp_path.joinpath("run-test").iterdir()} == {
        f"{agent_id}.pth" for agent_id in agents.ids()
    }
