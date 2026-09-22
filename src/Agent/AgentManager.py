import random

from src.Agent.agent import Agent
from src.Agent.identity import make_agent_id, new_run_id
from src.Agent.life import Life
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

    def __init__(self, world, rng=None, run_id=None, life=None, view_size=7):
        self.world = world

        # One field of view for the whole population, handed to every body
        # like the life rules: a mind is sized to its input, so two bodies
        # seeing different windows could not share a species of networks.
        self.view_size = view_size

        # The life rules of this run - one object handed to every body that
        # is ever born here, so childhood, aging and starvation mean the
        # same thing for the first agent and for the last one.
        self.life = life if life is not None else Life.from_config()

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
    def spawn(self, count=1, birth_step=0, parents=None):
        """Creates `count` agents and returns them."""
        return [
            self._spawn_one(birth_step, parents) for _ in range(count)
        ]

    def _spawn_one(self, birth_step=0, parents=None):
        index = self._next_index
        self._next_index += 1

        agent = Agent(
            agent_id=make_agent_id(self.run_id, index),
            index=index,
            world=self.world,
            position=self._spawn_position(),
            life=self.life,
            birth_step=birth_step,
            parents=parents,
            view_size=self.view_size,
        )

        self.agents[agent.agent_id] = agent
        return agent

    def remove(self, agent_id):
        """Removes an agent from the run and returns it (None if unknown)."""
        return self.agents.pop(agent_id, None)

    # -----------------------------
    # STATE (CHECKPOINT)
    # -----------------------------
    def state(self):
        """Every body alive, and the index counter that keeps ids unique."""
        return {
            "next_index": self._next_index,
            "world_id": self.run_id,
            "agents": [
                {
                    "agent_id": agent.agent_id,
                    "index": agent.index,
                    "position": agent.get_position(),
                    "energy": agent.energy,
                    "age": agent.age,
                    "birth_step": agent.birth_step,
                    "parents": list(agent.parents),
                    "total_reward": agent.total_reward,
                    "offspring": agent.offspring,
                }
                for agent in self.all()
            ],
        }

    def restore(self, state):
        """
        Puts the saved bodies back where they stood.

        No spawn draws happen here, and that is the point: a restored
        population must not consume the population stream, or the first
        birth after a resume would land somewhere the saved run would never
        have put it.

        The index counter is restored too. An index is never reused - it
        names an agent's private rng streams, so handing out 0 again would
        give a newborn the mind of the agent that already holds it.
        """
        self.run_id = state.get("world_id", self.run_id)
        self.agents = {}

        for record in state["agents"]:
            agent = Agent(
                agent_id=record["agent_id"],
                index=record["index"],
                world=self.world,
                position=Position(*record["position"]),
                life=self.life,
                birth_step=record["birth_step"],
                parents=record["parents"],
                view_size=self.view_size,
            )
            agent.energy = record["energy"]
            agent.age = record["age"]
            agent.total_reward = record["total_reward"]
            agent.offspring = record["offspring"]

            self.agents[agent.agent_id] = agent

        self._next_index = state["next_index"]

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
