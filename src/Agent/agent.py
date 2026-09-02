from src.Agent.State.observation import Observation

from src.Agent.Actions.movement.available_movements import get_available_movements
from src.Agent.Actions.movement.movements import MOVEMENTS

from src.world.Grid_world.objects import AGENT_CELL


class Agent:
    """
    One body in the world: a position, a field of view and a way to say
    where it wants to go.

    The agent does NOT decide where it spawns and does NOT invent its own
    id - both come from AgentManager, the single owner of agent identity.

    agent_id is globally unique across every run of the project and is the
    only thing that identifies an agent anywhere outside this process.
    index is its plain number inside this run, kept for the places that
    genuinely want a small integer (picking a color, printing a line).
    """

    def __init__(self, agent_id, index, world, position):
        self.agent_id = agent_id
        self.index = index
        self.world = world
        self.position = position

    # -----------------------------
    # MOVEMENT (INTENT -> APPLY)
    # -----------------------------
    def intended_position(self, action):
        """
        Where this action WOULD take the agent - nothing is applied here.

        Intent and application are split because a tick has to be resolved
        as a whole: the env first collects what every agent wants, then
        decides what actually happens, and only then moves anybody. Today
        every intent is granted, but a movement rule (blocking, pushing,
        swapping) has a single place to live because of this split.

        An impossible action - unknown id or a step outside the map -
        resolves to the current position: the agent simply stays put.
        """
        x, y = self.position.get()

        if action not in MOVEMENTS:
            return (x, y)

        dx, dy = MOVEMENTS[action]
        nx, ny = x + dx, y + dy

        # hard bounds check
        if not (0 <= nx < self.world.size and 0 <= ny < self.world.size):
            return (x, y)

        return (nx, ny)

    def move_to(self, position):
        self.position.update(position)

    # -----------------------------
    # POSITION
    # -----------------------------
    def get_position(self):
        return self.position.get()

    # -----------------------------
    # AVAILABLE ACTIONS
    # -----------------------------
    def get_available_actions(self):
        return get_available_movements(
            self.get_position(),
            self.world.size
        )

    # -----------------------------
    # OBSERVATION (STATE)
    # -----------------------------
    def get_state(self, agent_positions=None):
        """
        agent_positions: where every body stands, as ONE snapshot of the
        whole population. The env takes it after the tick has settled and
        hands the same snapshot to everybody, so no agent sees a world in
        which some have already moved and others have not.
        """
        pos = self.get_position()

        map_view = self.get_local_view(
            self.world.map.grid,
            pos,
            size=7
        )
        local_view = self.overlay_agents(
            map_view,
            pos,
            agent_positions,
            size=7
        )

        return Observation(pos, local_view, map_view)

    # -----------------------------
    # LOCAL VIEW (VISION)
    # -----------------------------
    @staticmethod
    def get_local_view(grid, position, size=7):
        x, y = position
        half = size // 2

        view = []

        for dy in range(-half, half + 1):
            row = []
            for dx in range(-half, half + 1):
                nx, ny = x + dx, y + dy

                if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]):
                    row.append(grid[ny][nx])
                else:
                    row.append(-1)

            view.append(row)

        return view

    @staticmethod
    def overlay_agents(map_view, position, agent_positions, size=7):
        """
        Paints the other bodies on top of a map view.

        A body HIDES the object it stands on - you cannot see through
        somebody. That is a real loss of information, and it is the honest
        price of showing agents as a cell value instead of a separate
        channel.

        The agent's own cell is never painted: it is always the center of
        the window, so marking it would spend a value on something the
        network can read off the geometry anyway.
        """
        agent_positions = agent_positions or set()

        x, y = position
        half = size // 2

        view = []

        for row_index, dy in enumerate(range(-half, half + 1)):
            row = list(map_view[row_index])

            for column, dx in enumerate(range(-half, half + 1)):
                cell = (x + dx, y + dy)

                if cell != position and cell in agent_positions:
                    row[column] = AGENT_CELL

            view.append(row)

        return view

    def __repr__(self):
        return (
            f"Agent(index={self.index}, id={self.agent_id}, "
            f"position={self.position.get()})"
        )
