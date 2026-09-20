import numpy as np
import yaml
from src.Genome.types.reuse import reuse

class NonLinearSpecies:
    partners_required = 1

    def mutate(self, genotype, rng):
        return reuse.mutate(genotype, rng)

    def reproduce(self, dad_genotype, mom_genotype, rng):
        alpha = mom_genotype["alpha"]
        
        child = {}
        for gene_name in dad_genotype:
            lo = min(mom_genotype[gene_name], dad_genotype[gene_name])   
            hi = max(mom_genotype[gene_name], dad_genotype[gene_name])
            d = hi - lo        
            child[gene_name] = rng.uniform(lo - alpha*d, hi + alpha*d)

        return reuse.mutate(child, rng)

    def make_first_genome(self, genome_config, rng):
        return reuse.make_first_genome(genome_config, rng)

    def make_phenotype(self, genotype):
        return reuse.make_phenotype(genotype)


