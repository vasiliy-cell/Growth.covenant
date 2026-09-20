import numpy as np
import yaml
from src.Genome.types.reuse import reuse


with open("config.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

class ClonSpecies:
    partners_required = 0

    def reproduce(self, dad_genotype, mom_genotype, rng):
        return reuse.mutate(dad_genotype, rng)

    def make_first_genome(self, genome_config, rng):
        return reuse.make_first_genome(genome_config, rng)

    def mutate(self, genotype, rng):
        return reuse.mutate(genotype, rng)

    def make_phenotype(self, genotype):
        return reuse.make_phenotype(genotype)




