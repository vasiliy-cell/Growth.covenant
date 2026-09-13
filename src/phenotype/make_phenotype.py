from src.Genome.types.clons import config

def make_phenotype(genotype):
    genome_config = config["genome"]
    phenotype = {}
    for name, value in genotype.items():
        if genome_config["genes"][name].get("type") == "int":
            value = round(value)    
        phenotype[name] = value
    return phenotype
