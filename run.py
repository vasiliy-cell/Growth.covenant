from world.world import World
from Agent.agent import Agent
from Brain.brain import Brain


def main():
    # --- мир ---
    world = World(size=8)
    world.generate()

    # --- агент ---
    agent = Agent(world)

    # --- мозг ---
    brain = Brain()

    print("=== START ===")
    world.print()

    # --- цикл ---
    for step in range(10):

        # 1. агент формирует состояние (Observation)
        observation = agent.get_state()

        # 2. мозг выбирает действие
        action = brain.choose_action(observation)

        # 3. агент выполняет действие
        agent.move(action)

        print(f"step {step}: pos={agent.get_position()}, action={action}")


if __name__ == "__main__":
    main()