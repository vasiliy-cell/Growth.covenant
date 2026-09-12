from src.Genome.types.clons import make_first_genome
from src.Genome.types.clons import config

import numpy as np

class Genepool:
    def __init__(self):
        self.gene_pool = {} 

    def get_genotype(self, agent_id):
        return self.genotype[agent_id]
    
    def get_genes_flag(self, agent_id):
        return self.genes_flag[agent_id]

    def put(self, agent_id, genome):
        self.gene_pool[agent_id] = genome

N = 12 # temporaly hardcoded N!!

def create_N_agents(N):
    genome_config = config["genome"]
    rng = np.random.default_rng(12)

    pool = Genepool()
    for i in range(N):
        agent_id = i
        aid, genome = make_first_genome(agent_id, genome_config, rng)
        pool.put(agent_id, genome)

    print(pool.gene_pool)

create_N_agents(N)