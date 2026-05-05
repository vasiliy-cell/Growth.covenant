from run import main
from visualization.renderer import Renderer

renderer = Renderer()

def render(env, info):
    renderer.render(env.world.map.grid, info["position"])

try:
    main(render_fn=render)
finally:
    renderer.close()