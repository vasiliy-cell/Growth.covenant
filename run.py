from world.world import World
from Agent.agent import Agent
from Brain.brain import Brain
from utils.logger import Logger


EPISODE_STEPS = 10


def main():

    episodes = int(input("Enter number of episodes: "))

    world = World(size=8)
    brain = Brain()

    print("\n=== SIMULATION START ===\n")

    for episode in range(episodes):

        world.generate()
        agent = Agent(world)
        logger = Logger()

        total_reward = 0

        for step in range(EPISODE_STEPS):

            # perception
            observation = agent.get_state()

            # action space
            available_actions = agent.get_available_actions()

            # decision
            action = brain.choose_action(observation, available_actions)

            # environment step
            agent.move(action)

            position = agent.get_position()
            reward = world.get_reward(position)

            total_reward += reward

            # logging
            logger.log_step(
                step=step,
                position=position,
                action=action,
                reward=reward,
                available_actions=available_actions
            )

        logger.end_episode()

        print(f"Episode {episode + 1}/{episodes} | total_reward={total_reward}")


if __name__ == "__main__":
    main()