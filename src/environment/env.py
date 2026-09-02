import random

from src.world.world import World
from src.Agent.AgentManager import AgentManager


class GridWorldEnv:
    """
    One continuous world shared by the whole population. No episodes, no
    reset:
      - the map is generated exactly once, in start(),
      - the agents are created once and keep their positions forever,
      - instead of regeneration the world refills itself (World.maybe_refill).

    The step API is PARALLEL: one call to step() is one tick of the world in
    which every agent acts simultaneously. Actions come in keyed by agent id
    and observations/rewards go back out the same way.

    A per-agent step(agent_id, action) was the other option and it is a trap:
    it would advance the clock - and with it the refill check - once per
    agent instead of once per tick, and it would hand whoever moved first a
    permanent advantage.
    """

    def __init__(self, size=8, rng=None, empty_ratio=0.8, refill=None,
                 agent_count=1, run_id=None):
        self.size = size

        # Single RNG for the whole run
        self.rng = rng if rng is not None else random.Random()

        self.world = World(size=size, empty_ratio=empty_ratio, refill=refill)
        self.agents = AgentManager(self.world, rng=self.rng, run_id=run_id)
        self.agent_count = agent_count

        self.current_step = 0

    # --- build the world (call once at the beginning of the run) ---
    def start(self):
        if len(self.agents) > 0:
            # Already running: never rebuild the world mid-run
            return self.get_states()

        self.world.generate(rng=self.rng)

        # Spawn AFTER the map is generated: the map keeps consuming the rng
        # in the same order as before, so old seeds still produce old maps.
        self.agents.spawn(self.agent_count)
        self.current_step = 0

        return self.get_states()

    def get_states(self):
        """{agent_id: Observation} for every agent, in id order."""
        return {agent.agent_id: agent.get_state() for agent in self.agents}

    def get_available_actions(self):
        return {
            agent.agent_id: agent.get_available_actions()
            for agent in self.agents
        }

    # --- one tick of the world: everybody moves at once ---
    def step(self, actions):
        """
        actions: {agent_id: action}. An agent missing from the dict simply
                 does not act this tick.

        Returns (observations, rewards, info): the first two are keyed by
        agent id, info describes the tick as a whole.
        """
        self.current_step += 1

        # 1. INTENT - where everyone WANTS to be, nothing applied yet.
        targets = {
            agent.agent_id: agent.intended_position(actions[agent.agent_id])
            for agent in self.agents
            if agent.agent_id in actions
        }

        # 2. RESOLVE - the movement rule of this world lives here.
        targets = self._resolve_movements(targets)

        # 3. APPLY
        for agent_id, position in targets.items():
            self.agents.get(agent_id).move_to(position)

        # 4. REWARDS - in a RANDOM order, never in id order. Agents may share
        #    a cell, so when two of them land on the same food the first one
        #    through this loop takes it and the cell turns empty for the
        #    other. Doing that in id order would make agent 0 permanently
        #    luckier than agent 49.
        rewards = {}

        for agent in self.agents.shuffled():
            position = agent.get_position()

            rewards[agent.agent_id] = self.world.get_reward(position)

            # good/bad cells turn empty once an agent touches them
            if self.world.get_cell(position) != 0:
                self.world.clear_cell(position)

        # Hand the rewards back in id order: the shuffle decides who eats
        # first, it must not also decide the order of the log lines.
        rewards = {
            agent_id: rewards[agent_id]
            for agent_id in self.agents.ids()
            if agent_id in rewards
        }

        # 5. REFILL - the world tops itself up once per TICK, however many
        #    agents there are, so world.refill.every keeps meaning what it
        #    meant with a single agent.
        refilled = self.world.maybe_refill(
            self.current_step,
            exclude=self.agents.occupied_positions(),
        )

        # 6. OBSERVE - only after the tick has fully settled, so every agent
        #    sees the same world state.
        observations = self.get_states()

        # No terminal state: this is a continuing task, so the training loop
        # always bootstraps (done=False) and stops only when total_steps is
        # reached.
        info = {
            "step": self.current_step,
            "positions": self.agents.positions(),
            "available_actions": self.get_available_actions(),
            "refilled": refilled,
            "non_empty_ratio": self.world.non_empty_ratio(),
        }
        return observations, rewards, info

    def _resolve_movements(self, targets):
        """
        Turns what the agents WANT into what actually happens.

        Right now the world is permissive: nobody blocks anybody, two agents
        may stand on the same cell and every intent is granted unchanged.
        This is the one and only place a stricter rule belongs - blocking,
        pushing, swap prevention - and adding one here changes nothing else
        in the codebase.
        """
        return targets

    # --- action space ---
    def get_action_space(self):
        return list(range(8))

    # --- observation space ---
    def get_observation_space(self):
        return {
            "position": (self.size, self.size),
            "local_view": (7, 7)
        }
