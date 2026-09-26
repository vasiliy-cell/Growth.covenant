from src.Behavior.Choosing_partner import choose_partners, config


class Body:
    """Just enough of an agent for the matchmaker: an id and its energy."""

    def __init__(self, agent_id, energy, position=(0, 0)):
        self.agent_id = agent_id
        self.energy = energy
        self.position = position

    def get_position(self):
        return self.position


def bodies(*energies, positions=None):
    positions = positions or [(0, 0)] * len(energies)
    return [Body(str(i), energy, positions[i]) for i, energy in enumerate(energies)]


def threshold():
    return config["energy"]["reproduction_threshold"]


def test_only_those_who_can_afford_a_child_are_paired():
    rich, poor = threshold(), threshold() - 1

    couples = choose_partners(bodies(rich, poor, rich, poor))

    assert [(a.agent_id, b.agent_id) for a, b in couples] == [("0", "2")]


def test_distance_does_not_matter():
    """
    Pairing by proximity selected for the crowds in the corners, where
    partners are always within reach, and left a good forager working an
    empty stretch of map without one.
    """
    rich = threshold()
    far_apart = bodies(rich, rich, positions=[(0, 0), (63, 63)])

    assert len(choose_partners(far_apart)) == 1


def test_an_odd_one_out_waits_for_the_next_tick():
    rich = threshold()

    couples = choose_partners(bodies(rich, rich, rich))

    assert len(couples) == 1
    assert "2" not in [agent.agent_id for pair in couples for agent in pair]


def test_nobody_breeds_twice_in_one_tick():
    rich = threshold()

    couples = choose_partners(bodies(rich, rich, rich, rich))
    paired = [agent.agent_id for pair in couples for agent in pair]

    assert len(couples) == 2
    assert len(set(paired)) == len(paired)
