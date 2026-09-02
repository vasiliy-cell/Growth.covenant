from run import main
from visualization.renderer import Renderer


def main_visual():
    renderer = Renderer()

    def render(env, info):
        # safety checks (ВАЖНО)
        if env is None or info is None:
            return

        if not hasattr(env.world.map, "grid"):
            print("NO GRID FOUND")
            return

        # Keyed by index, not by agent id: the renderer only needs a stable
        # small number to pick a color from, and the global id says nothing
        # about which color an agent should keep.
        renderer.render(
            env.world.map.grid,
            {agent.index: agent.get_position() for agent in env.agents}
        )

    try:
        main(render_fn=render)
    finally:
        renderer.close()


if __name__ == "__main__":
    main_visual()