import numpy as np
import yaml
from src.Genome.types.reuse import reuse

class NonLinearSpecies:
    partners_required = 1

    def __init__(self, evolve):
        # The genes that vary; every other gene is frozen at its mean. A
        # frozen gene is the same in both parents, so the blend below
        # hands it on as it is.
        self.evolve = evolve

    def mutate(self, genotype, rng):
        return reuse.mutate(genotype, rng, self.evolve)

    def reproduce(self, dad_genotype, mom_genotype, rng):
        alpha = mom_genotype["alpha"]
        
        child = {}
        for gene_name in dad_genotype:
            lo = min(mom_genotype[gene_name], dad_genotype[gene_name])   
            hi = max(mom_genotype[gene_name], dad_genotype[gene_name])
            d = hi - lo        
            child[gene_name] = rng.uniform(lo - alpha*d, hi + alpha*d)

        return reuse.mutate(child, rng, self.evolve)

    def make_first_genome(self, genome_config, rng):
        return reuse.make_first_genome(genome_config, rng, self.evolve)

    def make_phenotype(self, genotype, rng):
        # rng is part of the species interface, not of this species: only
        # mendel has to toss a coin to read a genotype (equal alleles).
        return reuse.make_phenotype(genotype)


