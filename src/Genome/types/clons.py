import numpy as np
import yaml
from src.Genome.types.reuse import reuse


with open("config.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

class ClonSpecies:
    partners_required = 0

    def __init__(self, evolve):
        # The genes that vary; every other gene is frozen at its mean.
        self.evolve = evolve

    def reproduce(self, dad_genotype, mom_genotype, rng):
        return reuse.mutate(dad_genotype, rng, self.evolve)

    def make_first_genome(self, genome_config, rng):
        return reuse.make_first_genome(genome_config, rng, self.evolve)

    def mutate(self, genotype, rng):
        return reuse.mutate(genotype, rng, self.evolve)

    def make_phenotype(self, genotype, rng):
        # rng is part of the species interface, not of this species: only
        # mendel has to toss a coin to read a genotype (equal alleles).
        return reuse.make_phenotype(genotype)




