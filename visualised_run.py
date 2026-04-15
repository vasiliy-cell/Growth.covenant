from world.world import World
from Agent.agent import Agent
from Brain.brain import Brain
from visualization.renderer import Renderer
from utils.logger import Logger   

EPISODE_STEPS = 10


def main():

    episodes = int(input("Enter number of episodes: "))

    world = World(size=8)
    brain = Brain()
    renderer = Renderer()

    for episode in range(episodes):

        world.generate()
        agent = Agent(world)

        logger = Logger()

        total_reward = 0

        print(f"\n=== Episode {episode+1} ===")

        for step in range(EPISODE_STEPS):

            try:
                observation = agent.get_state()
                action = brain.choose_action(observation)

                agent.move(action)

                position = agent.get_position()
                reward = world.get_reward(position)

                total_reward += reward

                logger.log_step(
                    step=step,
                    position=position,
                    action=action,
                    reward=reward,
                    available_actions=getattr(observation, "available_actions", None)
                )

                #  ВИЗУАЛ
                renderer.render(world.map.grid, position)

            except Exception as e:
                print(f"Error at step {step}: {e}")
                break

        logger.end_episode()

        print(f"Episode {episode+1} | total_reward={total_reward}")

    renderer.close()


if __name__ == "__main__":
    main()