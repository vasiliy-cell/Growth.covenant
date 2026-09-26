import yaml

with open("config.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)


def choose_partners(agents):
    """
    Who breeds with whom this tick: everybody who can afford a child,
    paired two by two.

    Energy is the whole of it, and distance is deliberately not. Pairing
    by proximity selected for the one thing this world already has too
    much of - bodies piling into the same corner - because a crowd is
    exactly where partners are always within reach, and a good forager
    working an empty stretch of map would never find one.

    An odd one out waits for the next tick, when whoever fed themselves
    up to the threshold in the meantime is standing next to it in the
    list.
    """
    threshold = config["energy"]["reproduction_threshold"]

    ready = [agent for agent in agents if agent.energy >= threshold]

    return list(zip(ready[::2], ready[1::2]))
