from src.Genome.types.reuse import make_first_genome
import numpy as np

import yaml

with open("config.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)
genome_config = config["genome"]

class MendelGeneticsSpecies:
    rng = np.random.default_rng()
    def make_first_mendel_genome(self, rng):
        
        draft_1 = make_first_genome(genome_config, rng)
        draft_2 = make_first_genome(genome_config, rng)

        # genome = {
        #     "some_gene": ((0.99, "A"), (0.95, "a")),
        #     "other":     ((64,   "a"), (70,   "A")),
        # }

        genotype = {}

        for gene_name in draft_1:
            draft_1[gene_name] = (draft_1[gene_name], str(rng.choice(["A", "a"])))
        for gene_name in draft_2:
            draft_2[gene_name] = (draft_2[gene_name], str(rng.choice(["A", "a"])))

        for gene_name in draft_2:
            genotype[gene_name] = ((draft_1[gene_name]),(draft_2[gene_name]))

            print(genotype)


rng = np.random.default_rng()
obj = MendelGeneticsSpecies()         
obj.make_first_mendel_genome(rng)