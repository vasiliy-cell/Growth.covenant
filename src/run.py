from src.environment.env import GridWorldEnv
from src.Brain.brain import Brain
from src.Brain.q_estimater.mlp import MLP
from src.Brain.q_estimater.trainer import DQNTrainer
from src.Brain.policy.policy import Policy
from src.Brain.reward_shaping.reward_shaping import RewardShaping
from src.Brain.reward_shaping.intrinsic_rewards.curiosity.curiosity import Curiosity
from src.utils.td_estimator import TDErrorLogger
from src.utils.logger import Logger
import yaml
import random
import time
import torch


def make_seed():
    return int(time.time() * 1e6)


def choose_seed():
    user_input = input("Enter seed (number or 'r' for random): ").strip()
    if user_input.lower() in ["r", ""]:
        return make_seed()
    try:
        return int(user_input)
    except ValueError:
        return make_seed()


def encode_observation(obs):
    x, y = obs.position
    flat = []
    for row in obs.local_view:
        for cell in row:
            flat.append(cell)
    return torch.tensor([x, y] + flat, dtype=torch.float32)


def main(render_fn=None):
    episodes = int(input("Enter number of episodes: "))
    seed = choose_seed() if episodes == 1 else make_seed()
    print(f"SEED: {seed}")

    master_rng = random.Random(seed)
    env = GridWorldEnv(size=8, max_steps=20, rng=master_rng)

    with open("src/Brain/config.yml", "r") as f:
        config = yaml.safe_load(f)

    dummy_obs = env.reset(seed=0)
    obs_size = len(encode_observation(dummy_obs))

    mlp = MLP(obs_size=obs_size, action_size=8)
    trainer = DQNTrainer(
        model=mlp,
        config=config
        # lr=config.get("lr", 0.001),
        # gamma=config["gamma"],
        # save_path="models/mlp.pth"
    )

    # epsilon-параметры берутся из config.yml, если они там есть,
    # иначе используются дефолты самого Policy.
    epsilon_cfg = config.get("epsilon", {})
    policy = Policy(
        epsilon=epsilon_cfg.get("start", 1.0),
        epsilon_decay=epsilon_cfg.get("decay", 0.995),
        epsilon_min=epsilon_cfg.get("min", 0.01)
    )

    brain = Brain(trainer, policy)

    reward_shaping = RewardShaping(
        curiosity=Curiosity(config["curiosity"]) if "curiosity" in config else None
    )

    for episode in range(episodes):
        # Новый Logger -> новый файл .jsonl на КАЖДЫЙ эпизод.
        # Имя файла генерируется внутри Logger по таймстампу,
        # так что коллизий между эпизодами не будет.
        logger = Logger()
        observation = env.reset(seed=master_rng.randint(0, 1_000_000))
        logger.log_seed(seed, episode_seed=episode)

        done = False
        total_reward = 0
        step_counter = 0

        while not done:
            state = encode_observation(observation)

            action = brain.choose_action(
                state,
                env.agent.get_available_actions()
            )

            next_obs, env_reward, done, info = env.step(action)

            shaped_reward, intrinsic_reward = reward_shaping.compute(next_obs, env_reward)

            brain.learn(
                state=state,
                action=action,
                reward=shaped_reward,
                next_state=encode_observation(next_obs),
                done=done
            )

            logger.log_step(
                step=step_counter,
                position=observation.position,
                action=action,
                reward=env_reward,
                shaped_reward=shaped_reward,
                intrinsic_reward=intrinsic_reward
            )

            total_reward += shaped_reward
            observation = next_obs
            step_counter += 1

            if render_fn is not None:
                render_fn(env, info)

        print(f"Episode {episode+1} | reward={total_reward} | epsilon={policy.epsilon:.4f}")

        logger.end_episode()  # пишет summary и закрывает файл этого эпизода

        # ВАЖНО: без этого вызова epsilon никогда не убывает — Policy
        # сам по себе не знает, когда эпизод закончился.
        policy.next_episode()

        if reward_shaping.curiosity is not None:
            reward_shaping.reset()

    trainer.save()
    print("Training finished")


if __name__ == "__main__":
    main()