import numpy as np
import yaml

genes_type = "clons"

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


