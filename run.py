from environment.env import GridWorldEnv
from Brain.brain import Brain
from utils.logger import Logger


def main():

    episodes = int(input("Enter number of episodes: "))

    env = GridWorldEnv(size=8, max_steps=10)
    brain = Brain()

    for episode in range(episodes):

        observation = env.reset()
        logger = Logger()

        total_reward = 0
        done = False
        step = 0

        while not done:

            available_actions = env.agent.get_available_actions()

            action = brain.choose_action(observation, available_actions)

            observation, reward, done, info = env.step(action)

            total_reward += reward

            logger.log_step(
                step=step,
                position=info["position"],
                action=action,
                reward=reward,
                available_actions=info["available_actions"]
            )

            step += 1

        logger.end_episode()

        print(f"Episode {episode + 1}/{episodes} | total_reward={total_reward}")


if __name__ == "__main__":
    main()