import torch

from src.Brain.brain import Brain
from src.Brain.policy.policy import Policy
from src.Brain.q_estimater.mlp import MLP
from src.Brain.q_estimater.group_trainer import GroupTrainer
from src.Brain.q_estimater.trainer import DQNTrainer
from src.Brain.replay_buffer import ReplayBuffer
from src.Brain.reward_shaping.reward_shaping import RewardShaping
from src.Brain.reward_shaping.intrinsic_rewards.curiosity.curiosity import Curiosity
from src.utils.rng import RunRandom


class BrainManager:
    """
    The registry of minds: one Brain per living agent.

    It mirrors AgentManager rather than living inside it, and that is
    deliberate. The world must not know that brains exist - env takes an
    action and hands back an observation, and nothing under src/world or
    src/environment has to import torch because of it. The two registries
    are tied together by the agent id and by nothing else.

    sync() follows the population instead of being told about it: an agent
    that appeared gets a mind, an agent that is gone has its mind written
    down and dropped. Birth and death therefore need no change here.

    Every mind is built from the streams of ITS agent (src/utils/rng.py),
    addressed by the agent's index: weights, exploration and replay
    sampling. That is what makes a run reproducible through birth and
    death - agent 7 gets the same mind whether it was the seventh of a
    crowd or the only body left alive.
    """
    def __init__(self, config, obs_size, action_size, checkpoints=None, rng=None):

        self.config = config
        self.obs_size = obs_size
        self.action_size = action_size
        self.checkpoints = checkpoints
        self.rng = rng if rng is not None else RunRandom(0)
        self.brains = {}

        # group key -> (member ids, GroupTrainer); see learn()
        self.groups = {}


    # -----------------------------
    # FOLLOWING THE POPULATION
    # -----------------------------
    def sync(self, agents, phenotypes):
        for agent in agents:
            if agent.agent_id not in self.brains:
                self.brains[agent.agent_id] = self._create(
                    phenotypes[agent.agent_id], agent.index
                )

        living = set(agents.ids())
        for agent_id in [i for i in self.brains if i not in living]:
            self.retire(agent_id)

    def retire(self, agent_id):
        """
        A mind leaves the run: written down first, dropped second.

        Saving here rather than only at the end of the run is the whole
        reason this exists. Otherwise only the survivors would ever reach
        the disk and the population on record would be silently selected
        for success.
        """
        brain = self.brains.pop(agent_id)

        if self.checkpoints is not None:
            self.checkpoints.save(agent_id, brain)

        return brain

    def _create(self, phenotype, index):
        return Brain(
            policy=Policy(
                epsilon=phenotype["epsilon"],
                epsilon_decay=phenotype["epsilon_decay"],
                epsilon_min=phenotype["epsilon_min"],
                generator=self.rng.torch("agent", index, "policy"),
            ),
            replay_buffer=ReplayBuffer(
                capacity=phenotype["buffer_size"],
                rng=self.rng.python("agent", index, "replay"),
            ),
            reward_shaping=RewardShaping(
                curiosity=Curiosity(
                    beta=phenotype["curiosity_beta"],
                    decay=phenotype["curiosity_decay"],
                ),
                food_bonus=float(
                    self.config.get("reward_shaping", {}).get("food_bonus", 0.0)
                ),
            ),
            batch_size=phenotype["batch_size"],
            min_buffer_size=phenotype["min_buffer_size"],

            trainer=DQNTrainer(
                model=self._build_model(phenotype, index),
                gamma=phenotype["gamma"],
                learning_rate=phenotype["learning_rate"],
                max_norm=phenotype["max_norm"],
                target_update_freq=phenotype["target_update_freq"],
            ),
        )


    def _build_model(self, phenotype, index):
        """
        This agent's network, with this agent's weights.

        torch builds a layer from the GLOBAL generator and takes no
        generator argument, so the only way to give one mind its own
        weights is to fork the global state, seed the fork from this
        agent's stream and let it go back to what it was afterwards.
        """
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(self.rng.seed_for("agent", index, "brain"))

            return MLP(
                obs_size=self.obs_size,
                hidden_size=phenotype["hidden_size"],
                hidden_layers=phenotype["hidden_layers"],
                action_size=self.action_size,
            )

    # -----------------------------
    # LEARNING
    # -----------------------------
    def learn(self, agent_ids):
        """
        One update for every mind in agent_ids that is past its warmup.
        Returns {agent_id: metrics}; a mind still warming up is left out.

        Minds that can learn side by side (Brain.group_key: same network
        shape, same batch size) are updated together by one GroupTrainer;
        a mind with no partner learns alone, exactly as Brain.learn does.
        Either way every mind takes the update it would take on its own -
        a group only does the arithmetic of its members in one batch.

        A group is kept from tick to tick while its membership stays the
        same, and rebuilt when it changes: somebody finished warming up,
        died, or was born into it.
        """
        members = {}

        for agent_id in agent_ids:
            brain = self.brains[agent_id]

            if brain.ready_to_learn():
                members.setdefault(brain.group_key(), []).append(agent_id)

        wanted = {key: tuple(ids) for key, ids in members.items() if len(ids) > 1}

        for key in list(self.groups):
            ids, group = self.groups[key]

            if wanted.get(key) != ids:
                group.dissolve()
                del self.groups[key]

        for key, ids in wanted.items():
            if key not in self.groups:
                group = GroupTrainer([self.brains[i].trainer for i in ids])
                self.groups[key] = (ids, group)

        metrics = {}

        for key, ids in members.items():
            if key in self.groups:
                batches = [self.brains[i].sample_batch() for i in ids]
                metrics.update(zip(ids, self.groups[key][1].update(batches)))
            else:
                metrics[ids[0]] = self.brains[ids[0]].learn()

        return metrics

    # -----------------------------
    # LOGGING WINDOW BOUNDARY
    # -----------------------------
    def next_episode(self):
        for brain in self.brains.values():
            brain.next_episode()

    # -----------------------------
    # ACCESS
    # -----------------------------
    def get(self, agent_id):
        return self.brains[agent_id]

    def items(self):
        return self.brains.items()

    def __len__(self):
        return len(self.brains)

    def __iter__(self):
        return iter(self.brains.values())

    def __contains__(self, agent_id):
        return agent_id in self.brains

    def __repr__(self):
        return f"BrainManager(minds={len(self.brains)})"
