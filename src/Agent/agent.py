from src.Agent.State.observation import Observation
from src.Agent.life import Life

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

    A body also has an age and it is personal: it counts the ticks THIS
    agent has lived, not the ticks of the run, so an agent born late is a
    child while the veterans around it are already paying for old age.
    What that age costs is not decided here - the agent only carries the
    number and asks its Life rules (src/Agent/life.py) for the answer.
    """

    def __init__(self, agent_id, index, world, position, life=None,
                 birth_step=0, parents=None, view_size=7):
        self.agent_id = agent_id
        self.index = index
        self.world = world
        self.position = position

        # Side of the square window this body sees, centered on itself -
        # odd, so there is a center. It decides how much of the map a mind
        # can plan over: a window that covers a small map almost whole is a
        # keyhole on a big one.
        self.view_size = view_size

        # Who made it and when. A body that was there from the first tick
        # has no parents and was born at step 0 - the run is its parent.
        self.birth_step = birth_step
        self.parents = list(parents or [])

        # The two numbers a life is judged by, kept on the body because
        # nothing else outlives the mind: the world reward this agent has
        # eaten in total, and how many children it paid for.
        self.total_reward = 0.0
        self.offspring = 0

        # The age this body first bred at, and None while it never has.
        # Breeding ends childhood however young the parent is, so this is
        # what the life rules read instead of the world's max_childhood_steps.
        self.adult_at = None

        # Ticks lived. Starts at 0 for everybody - a newborn is a newborn
        # whether it was spawned at the start of the run or born into it.
        self.age = 0

        # The biology of this world, shared by the whole population.
        self.life = life if life is not None else Life.from_config()

        # What it takes into the world. A body born at zero would already
        # be at the starvation threshold, so this is what makes death by
        # hunger a thing an agent can avoid rather than a countdown.
        self.energy = self.life.start_energy

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
    # LIFE (AGE -> LEAK -> DEATH)
    # -----------------------------
    def grow_older(self):
        """One tick lived. Called once per tick by the env, for everybody."""
        self.age += 1

    def grow_up(self):
        """Childhood ends here, whatever the age: this body has bred."""
        if self.adult_at is None:
            self.adult_at = self.age

    def is_child(self):
        """Still inside the immortal period - nothing can kill this agent."""
        return self.life.is_child(self.age, self.adult_at)

    def energy_leak(self):
        """What this body pays for being alive this tick: base cost + age."""
        return self.life.leak(self.age, self.adult_at)

    def is_dead(self):
        """An adult that has run out of energy. A child never is."""
        return self.life.is_dead(self.age, self.energy, self.adult_at)

    def life_summary(self, step, cause="starvation"):
        """
        The whole life in one record, for the moment it ends.

        cause is starvation and only starvation: it is the one way out of
        this world. Everything else that could go wrong for an agent -
        walking into danger, ageing, losing a cell to a neighbour - ends
        here, as energy it could not replace.
        """
        return {
            "agent_id": self.agent_id,
            "index": self.index,
            "parents": list(self.parents),
            "birth_step": self.birth_step,
            "death_step": step,
            "lifespan": self.age,
            "cumulative_reward": self.total_reward,
            "num_offspring": self.offspring,
            "cause_of_death": cause,
            "energy": self.energy,
        }

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
            size=self.view_size
        )
        local_view = self.overlay_agents(
            map_view,
            pos,
            agent_positions,
            size=self.view_size
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
            f"position={self.position.get()}, age={self.age}, "
            f"energy={self.energy:.1f})"
        )
