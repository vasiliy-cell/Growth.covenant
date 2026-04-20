import random

from world.world import World
from Agent.agent import Agent


class GridWorldEnv:
    def __init__(self, size=8, max_steps=10, rng=None):
        self.size = size
        self.max_steps = max_steps

        # Global RNG for the whole run
        self.master_rng = rng if rng is not None else random.Random()

        self.world = World(size=size)
        self.agent = None

        self.current_step = 0
        self.rng = None

    # --- reset environment ---
    def reset(self, seed=None):
        # Create RNG for this episode
        if seed is not None:
            self.rng = random.Random(seed)
        else:
            self.rng = self.master_rng

        # Delegate world generation to World (clean encapsulation)
        self.world.generate(rng=self.rng)

        # Create new agent in the generated world
        self.agent = Agent(self.world)

        self.current_step = 0

        return self.agent.get_state()

    # --- one step in environment ---
    def step(self, action):
        self.current_step += 1

        self.agent.move(action)

        observation = self.agent.get_state()
        position = self.agent.get_position()

        reward = self.world.get_reward(position)

        done = self.current_step >= self.max_steps

        info = {
            "position": position,
            "available_actions": self.agent.get_available_actions()
        }

        return observation, reward, done, info

    # --- action space ---
    def get_action_space(self):
        return list(range(8))

    # --- observation space ---
    def get_observation_space(self):
        return {
            "position": (self.size, self.size),
            "local_view": (7, 7)
        }