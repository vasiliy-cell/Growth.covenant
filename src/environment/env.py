import random

from src.world.world import World
from src.Agent.agent import Agent


class GridWorldEnv:
    """
    One continuous world. No episodes, no reset:
      - the map is generated exactly once, in start(),
      - the agent is created once and keeps its position forever,
      - instead of regeneration the world refills itself (World.maybe_refill).
    """

    def __init__(self, size=8, rng=None, empty_ratio=0.8, refill=None):
        self.size = size

        # Single RNG for the whole run - no per-episode local seeds anymore
        self.rng = rng if rng is not None else random.Random()

        self.world = World(size=size, empty_ratio=empty_ratio, refill=refill)
        self.agent = None

        self.current_step = 0

    # --- build the world (call once at the beginning of the run) ---
    def start(self):
        if self.agent is not None:
            # Already running: never rebuild the world mid-run
            return self.agent.get_state()

        self.world.generate(rng=self.rng)
        self.agent = Agent(self.world)
        self.current_step = 0

        return self.agent.get_state()

    def get_state(self):
        return self.agent.get_state()

    # --- one step in environment ---
    def step(self, action):
        self.current_step += 1

        self.agent.move(action)

        observation = self.agent.get_state()
        position = self.agent.get_position()

        reward = self.world.get_reward(position)

        # good/bad cells turn empty once the agent touches them
        if self.world.get_cell(position) != 0:
            self.world.clear_cell(position)

        # the world tops itself up instead of being regenerated
        refilled = self.world.maybe_refill(self.current_step, exclude=position)

        # No terminal state: this is a continuing task, so the training loop
        # always bootstraps (done=False) and stops only when total_steps is
        # reached.
        info = {
            "step": self.current_step,
            "position": position,
            "available_actions": self.agent.get_available_actions(),
            "refilled": refilled,
            "non_empty_ratio": self.world.non_empty_ratio(),
        }
        return observation, reward, info

    # --- action space ---
    def get_action_space(self):
        return list(range(8))

    # --- observation space ---
    def get_observation_space(self):
        return {
            "position": (self.size, self.size),
            "local_view": (7, 7)
        }
