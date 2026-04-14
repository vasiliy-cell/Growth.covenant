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

    print("=== START ===")
    world.print()

    for step in range(10):

        observation = agent.get_state()
        action = brain.choose_action(observation)

        agent.move(action)

        position = agent.get_position()

        # пока reward можно заглушкой (позже world reward)
        reward = 0

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