
from world.world import World
from Agent.agent import Agent


class GridWorldEnv:
    def __init__(self, size=8, max_steps=10):
        self.size = size
        self.max_steps = max_steps

        self.world = World(size=size)
        self.agent = None

        self.current_step = 0

    # --- reset environment ---
    def reset(self):
        self.world.generate()
        self.agent = Agent(self.world)

        self.current_step = 0

        observation = self.agent.get_state()
        return observation

    # --- one step in environment ---
    def step(self, action):
        self.current_step += 1

        # move agent
        self.agent.move(action)

        # get new state
        observation = self.agent.get_state()
        position = self.agent.get_position()

        # reward from world
        reward = self.world.get_reward(position)

        # done condition
        done = self.current_step >= self.max_steps

        # extra debug info
        info = {
            "position": position,
            "available_actions": self.agent.get_available_actions()
        }

        return observation, reward, done, info

    # --- action space ---
    def get_action_space(self):
        # 8 directions (как у тебя сейчас)
        return list(range(8))

    # --- observation space (просто описание) ---
    def get_observation_space(self):
        return {
            "position": (self.size, self.size),
            "local_view": (7, 7)
        }