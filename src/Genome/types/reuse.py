import yaml

with open("config.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

class reuse: 
    def make_first_genome(genome_config, rng):
        genotype = {}

        for gene_name, spec in genome_config["genes"].items():
            genotype[gene_name] = rng.normal(spec["mean"], spec["scale"])

        if genotype["gamma"] <= 0: 
            genotype["gamma"] = 0.001
        if genotype["gamma"] >= 1: 
            genotype["gamma"] = 0.999

        if genotype["learning_rate"] < 0:
            genotype["learning_rate"] = abs(genotype["learning_rate"])

        if genotype["sigma"] <0:
            genotype["sigma"] = 0.01
            
        return genotype

    def mutate(genotype, rng):
        sigma = genotype["sigma"]
        mutated_genotype = {}
        for gene_name, value in genotype.items():
            mutated_genotype[gene_name] = rng.normal(value, sigma)

            if rng.random() < sigma:
                mutated_genotype[gene_name] *= rng.uniform(0.2, 5.0)

        if mutated_genotype["gamma"] <= 0: 
            mutated_genotype["gamma"] = 0.001
        if mutated_genotype["gamma"] >= 1: 
            mutated_genotype["gamma"] = 0.999

        if mutated_genotype["learning_rate"] < 0:
            mutated_genotype["learning_rate"] = abs(mutated_genotype["learning_rate"])

        if mutated_genotype["sigma"] <0:
            mutated_genotype["sigma"] = 0.01

        return mutated_genotype

    def make_phenotype(genotype):
        genome_config = config["genome"]
        phenotype = {}
        for name, value in genotype.items():
            if genome_config["genes"][name].get("type") == "int":
                value = round(value)    
            phenotype[name] = value
        return phenotype