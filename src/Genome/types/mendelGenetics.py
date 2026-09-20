from src.Genome.types.reuse import make_first_genome
import copy
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
        genotype = {}
        
        for gene_name in draft_1:
            draft_1[gene_name] = [draft_1[gene_name], str(rng.choice(["A", "a"]))]
        for gene_name in draft_2:
            draft_2[gene_name] = [draft_2[gene_name], str(rng.choice(["A", "a"]))]

        for gene_name in draft_2:
            genotype[gene_name] = [draft_1[gene_name],draft_2[gene_name]]
        return genotype

    def mendel_mutate(self, genotype, rng): 
        mutated_genotype = copy.deepcopy(genotype)   
        i = rng.choice([0, 1])  
        sigma = genotype["sigma"][i][0]
        for gene_name in genotype:
            if rng.random() < sigma: 
                i = rng.choice([0, 1])
                mutated_genotype[gene_name][i][0] *= rng.uniform(0.2, 5.0)  
            if rng.random() < sigma: 
                i = rng.choice([0, 1])
                apel = mutated_genotype[gene_name][i][1]
                if apel == "a":
                    apel = "A"
                elif apel == "A":
                    apel = "a"
                mutated_genotype[gene_name][i][1] = apel

            for i in range(2):
                if mutated_genotype["gamma"][i][0] <= 0: 
                    mutated_genotype["gamma"][i][0] = 0.001
                if mutated_genotype["gamma"][i][0] >= 1: 
                    mutated_genotype["gamma"][i][0] = 0.999
                if mutated_genotype["learning_rate"][i][0] < 0:
                    mutated_genotype["learning_rate"][i][0] = abs(mutated_genotype["learning_rate"][i][0])
                if mutated_genotype["sigma"][i][0] <0:
                    mutated_genotype["sigma"][i][0] = 0.01

        return mutated_genotype

    def reproduce(self, dad_genotype, mom_genotype, rng):
        child_genotype = copy.deepcopy(mom_genotype)
        dad_genotype = copy.deepcopy(dad_genotype) 
        mom_genotype = copy.deepcopy(mom_genotype)   

        for gene_name in mom_genotype:
            for i in range(2):
                child_genotype[gene_name][i] = (mom_genotype if rng.random() < 0.5 else dad_genotype)[gene_name][i]
        genotype = child_genotype
        child_genotype = self.mendel_mutate(child_genotype, rng)
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
        print(phenotype)
        return phenotype


rng = np.random.default_rng()          
obj = MendelGeneticsSpecies()
genome = obj.make_first_mendel_genome(rng)  
obj.mendel_mutate(genome, rng)   

dad_genotype = obj.make_first_mendel_genome(rng)  
mom_genotype = obj.make_first_mendel_genome(rng)  

child_genotype = obj.reproduce(dad_genotype, mom_genotype, rng)  
phenotype = obj.make_phenotype(child_genotype, rng) 
