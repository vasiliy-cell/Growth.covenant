import numpy as np
import yaml

from src.Genome.types.clons import mutate

class NonLinearSpecies:
    partners_required = 1

    def reproduce(self, dad_genotype, mom_genotype, rng):
        alpha = mom_genotype["alpha"]
        
        child = {}
        for gene_name in dad_genotype:
            lo = min(mom_genotype[gene_name], dad_genotype[gene_name])   
            hi = max(mom_genotype[gene_name], dad_genotype[gene_name])
            d = hi - lo        
            child[gene_name] = rng.uniform(lo - alpha*d, hi + alpha*d)

        return mutate(child, rng)


