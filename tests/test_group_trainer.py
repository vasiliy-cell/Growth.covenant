import copy
import random

import torch

from src.Brain.q_estimater.group_trainer import GroupTrainer
from src.Brain.q_estimater.mlp import MLP
from src.Brain.q_estimater.trainer import DQNTrainer


OBS, BATCH = 12, 8


def make_trainers():
    """Same shape, everything else of their own."""
    torch.manual_seed(0)
    settings = [
        (0.99, 1e-3, 0.01, 3),
        (0.95, 5e-4, 1.0, 5),
        (0.999, 2e-3, 0.001, 2),
    ]

    return [
        DQNTrainer(MLP(OBS, 16, 8, 2), gamma, lr, max_norm, target_update_freq)
        for gamma, lr, max_norm, target_update_freq in settings
    ]


def make_batch(rng):
    return (
        tuple(torch.tensor([rng.random() for _ in range(OBS)]) for _ in range(BATCH)),
        tuple(rng.randrange(8) for _ in range(BATCH)),
        tuple(rng.uniform(-5, 5) for _ in range(BATCH)),
        tuple(torch.tensor([rng.random() for _ in range(OBS)]) for _ in range(BATCH)),
        tuple(False for _ in range(BATCH)),
    )


def assert_same(left, right):
    for a, b in zip(left.parameters(), right.parameters()):
        assert torch.allclose(a, b, atol=1e-6), (a - b).abs().max()


def test_group_update_matches_every_trainer_alone():
    alone = make_trainers()
    grouped = copy.deepcopy(alone)

    # one solo step first, so the group also takes over a warm Adam state
    rng = random.Random(1)
    for trainer, twin in zip(alone, grouped):
        batch = make_batch(rng)
        trainer.update(*batch)
        twin.update(*batch)

    group = GroupTrainer(grouped)
    rng = random.Random(2)

    for _ in range(12):
        batches = [make_batch(rng) for _ in alone]
        expected = [t.update(*b) for t, b in zip(alone, batches)]
        got = group.update(batches)

        for want, have in zip(expected, got):
            for key in want:
                assert abs(want[key] - have[key]) < 1e-4, key

    for trainer, twin in zip(alone, grouped):
        assert twin.training_step == trainer.training_step
        assert_same(trainer.policy_net, twin.policy_net)
        assert_same(trainer.target_net, twin.target_net)

        for a, b in zip(trainer.policy_net.parameters(), twin.policy_net.parameters()):
            mine, theirs = trainer.optimizer.state[a], twin.optimizer.state[b]
            assert float(mine["step"]) == float(theirs["step"])
            assert torch.allclose(mine["exp_avg"], theirs["exp_avg"], atol=1e-6)
            assert torch.allclose(mine["exp_avg_sq"], theirs["exp_avg_sq"], atol=1e-6)


def test_dissolved_members_learn_alone_and_own_their_numbers():
    trainers = make_trainers()
    group = GroupTrainer(trainers)
    rng = random.Random(3)

    group.update([make_batch(rng) for _ in trainers])
    group.dissolve()

    for trainer in trainers:
        for param in trainer.policy_net.parameters():
            assert param.data.untyped_storage().nbytes() == param.numel() * 4

        before = [p.clone() for p in trainer.policy_net.parameters()]
        trainer.update(*make_batch(rng))

        assert any(
            not torch.equal(a, b)
            for a, b in zip(before, trainer.policy_net.parameters())
        )


def test_state_of_a_grouped_mind_holds_only_its_own_numbers():
    trainers = make_trainers()
    group = GroupTrainer(trainers)
    group.update([make_batch(random.Random(4)) for _ in trainers])

    state = trainers[1].state()

    for tensor in list(state["policy_net"].values()) + list(state["target_net"].values()):
        assert tensor.untyped_storage().nbytes() == tensor.numel() * 4

    for slot in state["optimizer"]["state"].values():
        assert slot["exp_avg"].untyped_storage().nbytes() == slot["exp_avg"].numel() * 4


def test_group_q_values_match_every_net_alone():
    trainers = make_trainers()
    group = GroupTrainer(trainers)

    torch.manual_seed(7)
    states = torch.rand(len(trainers), OBS)
    q_values = group.q_values(states)

    for row, trainer in enumerate(trainers):
        with torch.no_grad():
            alone = trainer.policy_net(states[row])

        assert torch.allclose(q_values[row], alone, atol=1e-5)
