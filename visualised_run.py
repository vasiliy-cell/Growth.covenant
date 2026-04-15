import logging

from world.world import World
from Agent.agent import Agent
from Brain.brain import Brain
from visualization.renderer import Renderer


EPISODE_STEPS = 10


def setup_logger():
    logger = logging.getLogger("RL")
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S"
    )

    # вывод в консоль
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # запись в файл
    file_handler = logging.FileHandler("simulation.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def main():
    logger = setup_logger()

    episodes = int(input("Enter number of episodes: "))

    world = World(size=8)
    brain = Brain()
    renderer = Renderer()

    logger.info("Simulation started")

    for episode in range(episodes):

        world.generate()
        agent = Agent(world)

        logger.info(f"=== Episode {episode + 1} started ===")

        for step in range(EPISODE_STEPS):

            try:
                observation = agent.get_state()
                action = brain.choose_action(observation)

                logger.debug(
                    f"[Episode {episode+1} | Step {step}] "
                    f"State={observation} | Action={action}"
                )

                agent.move(action)
                position = agent.get_position()

                logger.info(
                    f"[Ep {episode+1} | Step {step}] Position={position}"
                )

                renderer.render(world.map.grid, position)

            except Exception as e:
                logger.error(
                    f"Error at Episode {episode+1}, Step {step}: {e}",
                    exc_info=True
                )
                break

        logger.info(f"=== Episode {episode + 1} finished ===")

    renderer.close()
    logger.info("Simulation finished")


if __name__ == "__main__":
    main()