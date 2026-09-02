import random

from src.Agent.agent import Agent
from src.Agent.identity import make_agent_id, new_run_id
from src.Agent.State.position import Position


class AgentManager:
    """
    The registry of every agent alive in the world.

    It is the single owner of agent identity: ids are handed out here and
    nowhere else. From here an id only travels UPWARDS - into the env API
    (actions/observations are keyed by it) and into the logs. Everything
    below the agent - world, map, rewards - never learns who moved: those
    layers work with positions, and they stay that way.

    Ids are globally unique, across every run this project ever makes (see
    src/Agent/identity.py), so an id in an old log always names exactly one
    agent in the whole history of the project.

    The population is not fixed. spawn() and remove() are part of the API
    from day one, so nothing downstream may assume a constant number of
    agents: adding death or birth later is a call, not a rewrite.
    """

    # How many random cells to try before giving up on a free one.
    SPAWN_ATTEMPTS = 100

    def __init__(self, world, rng=None, run_id=None):
        self.world = world

        # The same rng as the map and the refills: every draw the population
        # makes is part of the one reproducible stream of the run.
        self.rng = rng if rng is not None else random.Random()

        # The run this population belongs to. Passed in by the runner so the
        # logs and the agents carry the same id; minted here when a test or
        # a script builds a world on its own.
        self.run_id = run_id if run_id is not None else new_run_id()

        # agent_id -> Agent, in spawn order.
        self.agents = {}

        # Only ever counts upwards - an index is never reused, not even
        # after the agent that held it died.
        self._next_index = 0

    # -----------------------------
    # POPULATION
    # -----------------------------
    def spawn(self, count=1):
        """Creates `count` agents and returns them."""
        return [self._spawn_one() for _ in range(count)]

    def _spawn_one(self):
        index = self._next_index
        self._next_index += 1

        agent = Agent(
            agent_id=make_agent_id(self.run_id, index),
            index=index,
            world=self.world,
            position=self._spawn_position(),
        )

        self.agents[agent.agent_id] = agent
        return agent

    def remove(self, agent_id):
        """Removes an agent from the run and returns it (None if unknown)."""
        return self.agents.pop(agent_id, None)

    def _spawn_position(self):
        """
        A free cell for a newborn agent.

        Finding one is not a nicety, it is the world's invariant: the map
        holds one body per cell (GridWorldEnv._resolve_movements), and that
        has to be true from the very first tick, not just after the first
        move.

        The random draw comes first and the scan is only a fallback, so on a
        map with room to spare the very first agent consumes exactly the two
        rng draws a single agent used to consume - old seeds keep producing
        old runs.
        """
        occupied = self.occupied_positions()

        for _ in range(self.SPAWN_ATTEMPTS):
            position = Position.random(self.world.size, self.rng)

            if position.get() not in occupied:
                return position

        # Crowded map: scan for a free cell instead of rolling forever.
        for y in range(self.world.size):
            for x in range(self.world.size):
                if (x, y) not in occupied:
                    return Position(x, y)

        raise RuntimeError(
            f"No free cell for a new agent: {len(self.agents)} agents "
            f"already fill a {self.world.size}x{self.world.size} world"
        )

    # -----------------------------
    # ACCESS
    # -----------------------------
    def get(self, agent_id):
        return self.agents[agent_id]

    def ids(self):
        return list(self.agents.keys())

    def all(self):
        """Every agent in spawn order - the stable order for anything that is
        order-independent (applying moves, building observations, logging)."""
        return list(self.agents.values())

    def positions(self):
        return {
            agent_id: agent.get_position()
            for agent_id, agent in self.agents.items()
        }

    def occupied_positions(self):
        return {agent.get_position() for agent in self.agents.values()}

    def __len__(self):
        return len(self.agents)

    def __iter__(self):
        return iter(self.all())

    def __contains__(self, agent_id):
        return agent_id in self.agents

    def __repr__(self):
        return f"AgentManager(run={self.run_id}, alive={len(self.agents)})"
