import yaml


with open("config.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

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
    child_genotype = {}
    for gene_name, value in genotype.items():
        child_genotype[gene_name] = rng.normal(value, sigma)

        if rng.random() < sigma:
            child_genotype[gene_name] *= rng.uniform(0.2, 5.0)

    if child_genotype["gamma"] <= 0: 
        child_genotype["gamma"] = 0.001
    if child_genotype["gamma"] >= 1: 
        child_genotype["gamma"] = 0.999

    if child_genotype["learning_rate"] < 0:
        child_genotype["learning_rate"] = abs(child_genotype["learning_rate"])

    if child_genotype["sigma"] <0:
        child_genotype["sigma"] = 0.01

    return child_genotype
