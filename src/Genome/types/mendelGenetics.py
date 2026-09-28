from src.Genome.types.reuse import reuse
import copy
import numpy as np
import yaml

with open("config.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)
genome_config = config["genome"]

class MendelGeneticsSpecies:
    partners_required = 1
    rng = np.random.default_rng()

    def __init__(self, evolve):
        # The genes that vary; every other gene is frozen at its mean, in
        # both alleles and with its dominance as it was born.
        self.evolve = evolve

    def make_first_genome(self, genome_config, rng):
        draft_1 = reuse.make_first_genome(genome_config, rng, self.evolve)
        draft_2 = reuse.make_first_genome(genome_config, rng, self.evolve)
        genotype = {}
        
        for gene_name in draft_1:
            draft_1[gene_name] = [draft_1[gene_name], str(rng.choice(["A", "a"]))]
        for gene_name in draft_2:
            draft_2[gene_name] = [draft_2[gene_name], str(rng.choice(["A", "a"]))]

        for gene_name in draft_2:
            genotype[gene_name] = [draft_1[gene_name],draft_2[gene_name]]
        return genotype

    def mutate(self, genotype, rng): 
        mutated_genotype = copy.deepcopy(genotype)   
        i = rng.choice([0, 1])  
        sigma = genotype["sigma"][i][0]
        for gene_name in genotype:
            # A frozen gene takes the same draws and ignores them.
            frozen = gene_name not in self.evolve

            if rng.random() < sigma: 
                i = rng.choice([0, 1])
                factor = rng.uniform(0.5, 2.0)
                if not frozen:
                    mutated_genotype[gene_name][i][0] *= factor
            if rng.random() < sigma: 
                i = rng.choice([0, 1])
                apel = mutated_genotype[gene_name][i][1]
                if apel == "a":
                    apel = "A"
                elif apel == "A":
                    apel = "a"
                if not frozen:
                    mutated_genotype[gene_name][i][1] = apel

            for i in range(2):
                if mutated_genotype["gamma"][i][0] <= 0: 
                    mutated_genotype["gamma"][i][0] = 0.001
                if mutated_genotype["gamma"][i][0] >= 1: 
                    mutated_genotype["gamma"][i][0] = 0.999
                if mutated_genotype["learning_rate"][i][0] < 0:
                    mutated_genotype["learning_rate"][i][0] = 0.0001
                if mutated_genotype["sigma"][i][0] <0:
                    mutated_genotype["sigma"][i][0] = 0.01
                if mutated_genotype["alpha"][i][0] < 0:
                    mutated_genotype["alpha"][i][0] = 0.001
                if mutated_genotype["max_norm"][i][0] < 0:
                    mutated_genotype["max_norm"][i][0] = 0.0001
                if mutated_genotype["epsilon_decay"][i][0] >= 1:
                    mutated_genotype["epsilon_decay"][i][0] = 0.999
                if mutated_genotype["curiosity_decay"][i][0] >= 1:
                    mutated_genotype["curiosity_decay"][i][0] = 0.999

        return mutated_genotype

    def reproduce(self, dad_genotype, mom_genotype, rng):
        child_genotype = copy.deepcopy(mom_genotype)
        dad_genotype = copy.deepcopy(dad_genotype) 
        mom_genotype = copy.deepcopy(mom_genotype)   

        # Segregation: exactly one allele from each parent, each picked at
        # random from that parent's two - slot 0 from the mother, slot 1
        # from the father.
        for gene_name in mom_genotype:
            child_genotype[gene_name][0] = mom_genotype[gene_name][rng.choice([0, 1])]
            child_genotype[gene_name][1] = dad_genotype[gene_name][rng.choice([0, 1])]
        genotype = child_genotype
        child_genotype = self.mutate(child_genotype, rng)
        return child_genotype

    def make_phenotype(self, child_genotype, rng):
        phenotype = copy.deepcopy(child_genotype)
        for gene_name in phenotype:
            if phenotype[gene_name][0][1] == phenotype[gene_name][1][1]:
                i = rng.choice([0, 1])
                phenotype[gene_name] = phenotype[gene_name][i][0]
            else:
                if phenotype[gene_name][0][1] == "A":
                    phenotype[gene_name] = phenotype[gene_name][0][0]
                elif phenotype[gene_name][1][1] == "A":
                    phenotype[gene_name] = phenotype[gene_name][1][0]

            if genome_config["genes"][gene_name].get("type") == "int":
                    phenotype[gene_name] = round(phenotype[gene_name])
        return phenotype

