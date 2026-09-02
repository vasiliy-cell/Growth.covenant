from src.Brain.brain import Brain
from src.Brain.policy.policy import Policy
from src.Brain.q_estimater.mlp import MLP
from src.Brain.q_estimater.trainer import DQNTrainer
from src.Brain.replay_buffer import ReplayBuffer
from src.Brain.reward_shaping.reward_shaping import RewardShaping
from src.Brain.reward_shaping.intrinsic_rewards.curiosity.curiosity import Curiosity


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
    """

    def __init__(self, config, obs_size, action_size, checkpoints=None):
        self.config = config
        self.obs_size = obs_size
        self.action_size = action_size
        self.checkpoints = checkpoints

        # agent_id -> Brain
        self.brains = {}

    # -----------------------------
    # FOLLOWING THE POPULATION
    # -----------------------------
    def sync(self, agents):
        """Gives every new agent a mind and retires the minds left over."""
        # Spawn order, never set order: creating a brain draws from the
        # torch rng to initialise its weights, so an unstable order would
        # quietly cost the run its reproducibility.
        for agent in agents:
            if agent.agent_id not in self.brains:
                self.brains[agent.agent_id] = self._create()

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

    def _create(self):
        policy_cfg = self.config.get("policy", {})
        buffer_cfg = self.config.get("replay_buffer", {})
        batch_size = buffer_cfg.get("batch_size", 32)

        return Brain(
            trainer=DQNTrainer(
                model=MLP(
                    obs_size=self.obs_size,
                    action_size=self.action_size
                ),
                config=self.config
            ),
            policy=Policy(
                epsilon=policy_cfg.get("epsilon", 1.0),
                epsilon_decay=policy_cfg.get("epsilon_decay", 0.995),
                epsilon_min=policy_cfg.get("epsilon_min", 0.01)
            ),
            replay_buffer=ReplayBuffer(
                capacity=buffer_cfg.get("buffer_size", 10_000)
            ),
            reward_shaping=RewardShaping(
                curiosity=Curiosity(self.config["curiosity"])
                if "curiosity" in self.config else None
            ),
            batch_size=batch_size,
            min_buffer_size=buffer_cfg.get("min_buffer_size", batch_size),
        )

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
