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

        renderer.render(
            env.world.map.grid,
            info.get("position", (0, 0))
        )

    try:
        main(render_fn=render)
    finally:
        renderer.close()


if __name__ == "__main__":
    main_visual()