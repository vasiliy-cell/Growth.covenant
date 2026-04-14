from world.world import World
from Agent.agent import Agent
from Brain.brain import Brain
from utils.logger import Logger

def main():
    world = World(size=8)
    world.generate()

    agent = Agent(world)
    brain = Brain()

    logger = Logger()

    world.print()

    for step in range(10):

        observation = agent.get_state()
        action = brain.choose_action(observation)

        agent.move(action)

        position = agent.get_position()
        reward = world.get_reward(position)

        logger.log_step(
            step=step,
            position=position,
            action=action,
            reward=reward,
            available_actions=observation.available_actions
        )

        print(f"step {step}: pos={position}, action={action}")

    logger.end_episode()



if __name__ == "__main__":
    main()