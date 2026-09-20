from src.Genome.types.reuse import config


class Life:
    """
    How long a body lasts: the rules that turn steps lived into an energy
    leak and, in the end, into a cause of death.

    A life has two periods, and the first one is free:

      - CHILDHOOD - the first `childhood_steps` ticks after birth. The agent
        ages and leaks energy like everybody else, but nothing can kill it.
        Every newborn therefore gets exactly the same amount of time to
        learn where the food is before the world starts charging for
        mistakes.
      - ADULTHOOD - everything after that. The agent is mortal, and
        starvation is the only way out: at or below `death_energy` it is
        removed from the run.

    There is no hard age limit and there does not need to be one: the leak
    grows by `aging_amount` every `aging_every` ticks of a life and never
    stops growing, so sooner or later it outruns anything an agent can
    forage. Old age here is not a number to compare against - it is a bill
    that keeps rising until it cannot be paid.

    One Life object is shared by the whole population: it describes the
    biology of this world, not one body. An agent carries only its own age
    and asks here what that age costs it.
    """

    def __init__(
        self,
        childhood_steps=300,
        base_leak=0.5,
        aging_every=200,
        aging_amount=0.05,
        death_energy=0.0,
    ):
        self.childhood_steps = childhood_steps
        self.base_leak = base_leak
        self.aging_every = aging_every
        self.aging_amount = aging_amount
        self.death_energy = death_energy

    @classmethod
    def from_config(cls, source=None):
        """The rules of this run, read from the `life` / `energy` sections."""
        source = source if source is not None else config

        life_cfg = source.get("life", {})
        aging_cfg = life_cfg.get("aging", {})

        return cls(
            childhood_steps=int(life_cfg.get("childhood_steps", 300)),
            base_leak=float(source.get("energy", {}).get("energy_leak", 0.5)),
            aging_every=int(aging_cfg.get("every", 200)),
            aging_amount=float(aging_cfg.get("amount", 0.05)),
            death_energy=float(life_cfg.get("death_energy", 0.0)),
        )

    # -----------------------------
    # PERIOD
    # -----------------------------
    def is_child(self, age):
        return age < self.childhood_steps

    # -----------------------------
    # AGING
    # -----------------------------
    def leak(self, age):
        """
        What being alive costs this body right now.

        A step function, not a smooth curve: the leak is the base cost plus
        one `aging_amount` for every full `aging_every` ticks already lived,
        so a whole generation born together ages in the same visible jumps.
        """
        if self.aging_every <= 0:
            return self.base_leak

        return self.base_leak + (age // self.aging_every) * self.aging_amount

    # -----------------------------
    # DEATH
    # -----------------------------
    def is_dead(self, age, energy):
        """Starvation, and only for an adult - childhood ignores energy."""
        if self.is_child(age):
            return False

        return energy <= self.death_energy

    def __repr__(self):
        return (
            f"Life(childhood={self.childhood_steps}, leak={self.base_leak}, "
            f"aging=+{self.aging_amount}/{self.aging_every}, "
            f"death_at={self.death_energy})"
        )
