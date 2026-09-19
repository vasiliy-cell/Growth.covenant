import numpy as np
import yaml

from src.Genome.types.reuse import mutate

with open("config.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

class ClonSpecies:
    partners_required = 0
    def reproduce(self, dad_genotype, mom_genotype, rng):
        return mutate(a, rng)      




