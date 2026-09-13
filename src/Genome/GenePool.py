
class Genepool:
    def __init__(self):
        self.gene_pool = {} 

    def get_genotype(self, agent_id):
        return self.gene_pool[agent_id]

    
    def get_genes_flag(self, agent_id):
        return self.genes_flag[agent_id]

    def put(self, agent_id, genome):
        self.gene_pool[agent_id] = genome



