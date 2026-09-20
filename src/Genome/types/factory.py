from src.Genome.types.clons import ClonSpecies
from src.Genome.types.non_linear import NonLinearSpecies
from src.Genome.types.mendelGenetics import MendelGeneticsSpecies


# name (from config) -> the Species class that implements that reproduction
# style. Adding a variant later = ONE line here + its class. Nothing else in
# the codebase branches on the species: everyone calls species.reproduce(...).
SPECIES = {
    "clons": ClonSpecies,
    "non_linear": NonLinearSpecies,
    "mendel": MendelGeneticsSpecies
}


def make_species(name):
    """Pick this run's reproduction strategy once, by config name."""
    return SPECIES[name]()

