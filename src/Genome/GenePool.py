
class Genepool:
    """
    Who carries what, for every agent alive in the run.

    Two things per agent and they are not the same thing:

      genotype  - the DNA, what this agent passes on,
      phenotype - how that DNA reads in this body, which is what the mind
                  was actually built from (network shape, learning rate,
                  epsilon schedule).

    The phenotype is kept and not re-derived on demand because reading a
    genotype can itself be a draw - mendel tosses a coin for every pair of
    equal alleles - so reading the same DNA twice is not guaranteed to
    give the same body, and a checkpoint that re-read it would rebuild a
    network the saved weights no longer fit.
    """

    def __init__(self):
        self.gene_pool = {}
        self.phenotypes = {}

    # -----------------------------
    # GENOTYPE (DNA)
    # -----------------------------
    def get_genotype(self, agent_id):
        return self.gene_pool[agent_id]

    def put(self, agent_id, genome):
        self.gene_pool[agent_id] = genome

    # -----------------------------
    # PHENOTYPE (THE BODY IT BUILT)
    # -----------------------------
    def get_phenotype(self, agent_id):
        return self.phenotypes[agent_id]

    def put_phenotype(self, agent_id, phenotype):
        self.phenotypes[agent_id] = phenotype

    def has_phenotype(self, agent_id):
        return agent_id in self.phenotypes

    def __len__(self):
        return len(self.gene_pool)
