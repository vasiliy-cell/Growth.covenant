from src.world.world import World
from src.Agent.AgentManager import AgentManager
from src.Agent.life import Life
from src.utils.rng import RunRandom

from src.Genome.types.reuse import reuse, config
from src.Genome.types.factory import make_species
from src.Behavior.Choosing_partner import choose_partners
from src.Genome.GenePool import Genepool


class GridWorldEnv:
    """
    One continuous world shared by the whole population. No episodes, no
    reset:
      - the map is generated exactly once, in start(),
      - the agents keep their positions for as long as they live - nobody
        is ever teleported back to a starting cell,
      - instead of regeneration the world refills itself (World.maybe_refill).

    The population is the only thing that turns over: a tick ends with the
    starved removed and the well-fed reproducing, so the run outlives the
    bodies that started it.

    The step API is PARALLEL: one call to step() is one tick of the world in
    which every agent acts simultaneously. Actions come in keyed by agent id
    and observations/rewards go back out the same way.

    A per-agent step(agent_id, action) was the other option and it is a trap:
    it would advance the clock - and with it the refill check - once per
    agent instead of once per tick, and it would hand whoever moved first a
    permanent advantage.
    """

    def __init__(self, size=8, rng=None, empty_ratio=0.8, refill=None, agent_count=1, run_id=None, species_name=None, life=None, view_size=7):
        self.size = size

        # Every stream of chance in this run (src/utils/rng.py). The world
        # asks it for named streams instead of sharing one: a fight over a
        # cell must not move the next refill, and a birth must not move
        # anything at all.
        self.rng = rng if rng is not None else RunRandom(RunRandom.new_seed())

        self.world_rng = self.rng.python("world")
        self.movement_rng = self.rng.python("movement")

        # Childhood, aging and starvation - one set of rules for everybody
        # born in this world (see the `life` section of config.yml).
        self.life = life if life is not None else Life.from_config(config)

        self.world = World(size=size, empty_ratio=empty_ratio, refill=refill)
        self.agents = AgentManager(
            self.world,
            rng=self.rng.python("population"),
            run_id=run_id,
            life=self.life,
            view_size=view_size,
        )
        self.agent_count = agent_count

        self.current_step = 0

        self.genomes = Genepool()

        # One numpy stream for everything genetic (genesis + mutation).
        self.genome_rng = self.rng.numpy("genome")

        # The reproduction strategy for this run, chosen ONCE by config.
        # Everything below calls self.species.reproduce(...) without ever
        # asking which species it is - that is the whole point.
        self.species_name = species_name or config["genome"]["type"]
        self.species = make_species(self.species_name)

    # --- build the world (call once at the beginning of the run) ---
    def start(self):
        if len(self.agents) > 0:
            # Already running: never rebuild the world mid-run
            return self.get_states()

        self.world.generate(rng=self.world_rng)

        # The map and the population draw from two different streams, so
        # the order of these two calls no longer decides what either of
        # them gets - only the seed does.
        self.agents.spawn(self.agent_count)
        self.create_agents()
        self.current_step = 0
        return self.get_states()


    def create_agents(self):
        genome_config = config["genome"]
        for agent_id in self.agents.ids():
            genome = self.species.make_first_genome(genome_config, self.genome_rng)
            self.genomes.put(agent_id, genome)

    def make_phenotype(self, agent_id):
        """
        How this genotype reads, in this body - read once and kept.

        The draw belongs to the agent and not to the run: mendel tosses a
        coin for every pair of equal alleles, and that toss must not depend
        on how many other agents were read before this one. The result is
        stored in the gene pool because reading the same DNA twice need not
        give the same body, and a checkpoint that re-read it would rebuild a
        network its saved weights no longer fit.
        """
        if self.genomes.has_phenotype(agent_id):
            return self.genomes.get_phenotype(agent_id)

        index = self.agents.get(agent_id).index

        phenotype = self.species.make_phenotype(
            self.genomes.get_genotype(agent_id),
            self.rng.numpy("agent", index, "phenotype"),
        )
        self.genomes.put_phenotype(agent_id, phenotype)

        return phenotype

    # -----------------------------
    # STATE (CHECKPOINT)
    # -----------------------------
    def state(self):
        """
        The world as one record: the map, the clock and every body on it.

        The species is in here because a genotype only means something to
        the species that wrote it - a mendel genome is pairs of alleles and
        a clon genome is plain numbers, so resuming one as the other would
        read nonsense out of the DNA.
        """
        population = self.agents.state()

        return {
            "world": self.world.state(),
            "refill": {
                "every": self.world.refill_every,
                "threshold": self.world.refill_threshold,
            },
            "current_step": self.current_step,
            "species": self.species_name,
            # The window every network of this world was sized to. A resume
            # must see through the same one, or the saved weights no longer
            # fit the input.
            "view_size": self.agents.view_size,
            "population": population,
            # make_phenotype and not get_phenotype: a body born on the
            # very tick that is being saved has DNA but has not been read
            # yet - its mind is built on the next tick. Reading it here
            # takes the draw that tick would have taken, from that agent's
            # own stream and nobody else's, and the result is cached, so
            # the run is not moved by having been saved.
            "genomes": {
                record["agent_id"]: {
                    "genotype": self.genomes.get_genotype(record["agent_id"]),
                    "phenotype": self.make_phenotype(record["agent_id"]),
                }
                for record in population["agents"]
            },
        }

    def restore(self, state):
        """
        Carries on the saved world instead of building a new one.

        This is start() for a run that already happened: nothing is
        generated and nothing is spawned, so not one draw is taken from any
        stream. Everything the streams had drawn by then is put back
        separately, by the checkpoint, after everything else is built.
        """
        self.world.restore(state["world"], rng=self.world_rng)
        self.size = self.world.size

        # A checkpoint from before the window was a setting was made with
        # the 7x7 view that used to be hardcoded.
        self.agents.view_size = state.get("view_size", 7)
        self.agents.restore(state["population"])

        for agent_id, genome in state["genomes"].items():
            self.genomes.put(agent_id, genome["genotype"])
            self.genomes.put_phenotype(agent_id, genome["phenotype"])

        self.current_step = state["current_step"]

        return self.get_states()

    # --- birth: reproduction driven by this run's species ---
    def _reproduce(self):
        """Returns one record per child born this tick, parents named."""
        cost = config["energy"]["reproduction_cost"]
        born = []

        if self.species.partners_required == 0:
            # asexual: everyone past the energy threshold clones itself
            threshold = config["energy"]["reproduction_threshold"]
            parents = [a for a in self.agents.all() if a.energy >= threshold]
            for parent in parents:
                genotype = self.genomes.get_genotype(parent.agent_id)
                child = self.species.reproduce(genotype, None, self.genome_rng)
                born.append(self._birth(child, cost, [parent]))
                parent.energy -= cost
        else:
            # sexual: choose_partners returns energy+proximity matched pairs
            for mother, father in choose_partners(self.agents):

                g_mother = self.genomes.get_genotype(mother.agent_id)
                g_father = self.genomes.get_genotype(father.agent_id)
                child = self.species.reproduce(g_father, g_mother, self.genome_rng)
                born.append(self._birth(child, cost, [mother, father]))
                mother.energy -= cost/2
                father.energy -= cost/2

        return born


    # --- death: starvation, the only way out of this world ---
    def _reap(self):
        """
        Removes everybody who starved this tick, and returns one whole
        life per body: where it came from, what it ate, what it left.

        Death comes BEFORE birth on purpose: an agent that cannot feed
        itself does not get to spend its last tick reproducing. Childhood is
        checked inside Agent.is_dead(), so a newborn survives this call
        whatever its energy is.

        The genome stays in the gene pool - the pool is the record of who
        lived in this run, and the run is allowed to outlive the body -
        and it is what a life summary carries out with it.
        """
        dead = [agent for agent in self.agents.all() if agent.is_dead()]
        records = []

        for agent in dead:
            self.agents.remove(agent.agent_id)

            record = agent.life_summary(self.current_step)
            record["genotype"] = self.genomes.get_genotype(agent.agent_id)
            records.append(record)

            print(
                f"[death @ step {self.current_step}] -> {agent.agent_id}  "
                f"(age {agent.age}, pop {len(self.agents)})"
            )

        return records

    def _birth(self, child_genotype, start_energy, parents):
        """
        Give a new child genome a body and register it in every registry.

        The parents are named on the child and counted on them: a lineage
        is the one thing about a population that cannot be reconstructed
        afterwards from anything else in the logs.
        """
        baby = self.agents.spawn(
            1,
            birth_step=self.current_step,
            parents=[parent.agent_id for parent in parents],
        )[0]

        self.genomes.put(baby.agent_id, child_genotype)
        baby.energy = start_energy

        for parent in parents:
            parent.offspring += 1

        print(f"[birth @ step {self.current_step}] -> {baby.agent_id}  (pop {len(self.agents)})")

        return {
            "agent_id": baby.agent_id,
            "index": baby.index,
            "parents": list(baby.parents),
            "energy": baby.energy,
            "genotype": child_genotype,
        }

    def get_states(self):
        """
        {agent_id: Observation} for every agent, in spawn order.

        The snapshot of positions is taken ONCE and shared: everybody sees
        the same frame of the world, nobody sees a half-moved population.
        """
        positions = self.agents.occupied_positions()

        return {
            agent.agent_id: agent.get_state(positions)
            for agent in self.agents
        }

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

        # 4. REWARDS. The order of this loop does not matter and cannot be
        #    made to matter: _resolve_movements guarantees one body per
        #    cell, so no two agents are ever standing on the same food and
        #    nobody can eat it from under anybody. Competition happens a
        #    step earlier, over who is allowed to move there at all.
        rewards = {}
        for agent in self.agents:
            position = agent.get_position()

            rewards[agent.agent_id] = self.world.get_reward(position)
            agent.energy += rewards[agent.agent_id]
            agent.total_reward += rewards[agent.agent_id]

            # good/bad cells turn empty once an agent touches them
            if self.world.get_cell(position) != 0:
                self.world.clear_cell(position)

            # The cost of being alive, and it is personal: the older the
            # body, the dearer the tick (src/Agent/life.py).
            agent.energy -= agent.energy_leak()

        # 4b. DEATH - starvation, once this tick's energy has settled.
        deaths = self._reap()

        # 4c. ONE TICK LIVED. Counted after the reaping and not before it,
        #     so a newborn is immortal for exactly life.childhood_steps
        #     ticks and the leak it paid above is the leak of the age it
        #     actually had while living this tick.
        for agent in self.agents:
            agent.grow_older()

        # 4d. BIRTH - energy-gated, on what is left alive.
        births = self._reproduce()

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

        # The world itself still has no terminal state - it never stops and
        # never resets, so a living agent always bootstraps (done=False).
        # Death is not a terminal state either, it is a removal: whoever is
        # in `died` simply has no next observation, and the run goes on
        # without them.
        info = {
            "step": self.current_step,
            "positions": self.agents.positions(),
            "available_actions": self.get_available_actions(),
            "refilled": refilled,
            "non_empty_ratio": self.world.non_empty_ratio(),
            "died": [record["agent_id"] for record in deaths],
            "deaths": deaths,
            "births": births,
            "alive": len(self.agents),
        }

        return observations, rewards, info

    def _resolve_movements(self, targets):
        """
        Turns what the agents WANT into what actually happens. This is the
        one and only place the movement rule of this world lives.

        Two rules, and together they are what makes the population a crowd
        instead of N walkers ignoring each other:

          - one body per cell: an agent may not step onto a cell somebody
            already stands on,
          - when several agents reach for the same free cell in the same
            tick, exactly one gets it and the rng picks who.

        "Already stands on" is read from ONE snapshot taken before anybody
        moves, so the outcome never depends on the order the agents are
        looked at - nobody gets an advantage for having spawned first. The
        price is that a column of agents crawls forward one cell per tick:
        the one in front leaves, and only on the next tick can the one
        behind follow it.
        """
        occupied = self.agents.occupied_positions()

        resolved = {}
        claims = {}

        # Staying put is always allowed - the agent is already there.
        # Stepping onto a taken cell never is.
        for agent_id, target in targets.items():
            current = self.agents.get(agent_id).get_position()

            if target == current or target in occupied:
                resolved[agent_id] = current
            else:
                claims.setdefault(target, []).append(agent_id)

        # One free cell, several claimants: the movement stream draws the
        # winner and everybody else stays where they are. That stream is the
        # only thing a fight consumes - the map and the minds never feel it.
        for target, claimants in claims.items():
            winner = (
                claimants[0] if len(claimants) == 1
                else self.movement_rng.choice(claimants)
            )

            for agent_id in claimants:
                resolved[agent_id] = (
                    target if agent_id == winner
                    else self.agents.get(agent_id).get_position()
                )

        return resolved

    # --- action space ---
    def get_action_space(self):
        return list(range(8))

    # --- observation space ---
    def get_observation_space(self):
        return {
            "position": (self.size, self.size),
            "local_view": (self.agents.view_size, self.agents.view_size)
        }
