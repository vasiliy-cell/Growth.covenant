import yaml

with open("config.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

class reuse: 
    def make_first_genome(genome_config, rng, evolve):
        """
        evolve: the genes that vary. Every other gene is frozen: each first
        agent gets exactly its mean. A frozen gene still takes its draw, so
        the genome stream is spent the same way whatever is frozen - one
        seed hands every other gene the same numbers in every condition.
        """
        genotype = {}

        for gene_name, spec in genome_config["genes"].items():
            value = rng.normal(spec["mean"], spec["scale"])
            genotype[gene_name] = value if gene_name in evolve else spec["mean"]

        if genotype["gamma"] <= 0: 
            genotype["gamma"] = 0.001
        if genotype["gamma"] >= 1: 
            genotype["gamma"] = 0.999

        if genotype["learning_rate"] < 0:
            genotype["learning_rate"] = 0.0001

        if genotype["sigma"] <0:
            genotype["sigma"] = 0.01

        if genotype["alpha"] < 0:
            genotype["alpha"] = 0.001

        if genotype["max_norm"] < 0:
            genotype["max_norm"] = 0.0001

        if genotype["epsilon_decay"] >= 1:
            genotype["epsilon_decay"] = 0.999
        if genotype["curiosity_decay"] >= 1:
            genotype["curiosity_decay"] = 0.999
            
        return genotype

    def mutate(genotype, rng, evolve):
        """
        The child's genome: the parent's, with a gene here and there
        multiplied by a number around 1.

        A gene changes with probability `sigma` and not otherwise, and it
        changes by a FACTOR, so the same sigma means the same thing to a
        learning rate of 0.001 and to a buffer of 10000. Adding a width in
        absolute units, which this used to do on every gene of every child,
        meant 90% of a learning rate and nothing at all of a buffer size.

        A gene outside `evolve` is frozen and passes on unchanged. It still
        takes its draws, the same as in make_first_genome.
        """
        sigma = genotype["sigma"]
        mutated_genotype = dict(genotype)

        for gene_name, value in genotype.items():

            if rng.random() < sigma:
                factor = rng.uniform(0.5, 2.0)

                if gene_name in evolve:
                    mutated_genotype[gene_name] = value * factor

        if mutated_genotype["gamma"] <= 0: 
            mutated_genotype["gamma"] = 0.001
        if mutated_genotype["gamma"] >= 1: 
            mutated_genotype["gamma"] = 0.999

        if mutated_genotype["learning_rate"] < 0:
            mutated_genotype["learning_rate"] = 0.0001

        if mutated_genotype["sigma"] <0:
            mutated_genotype["sigma"] = 0.01

        if mutated_genotype["alpha"] < 0:
            mutated_genotype["alpha"] = 0.001

        if mutated_genotype["max_norm"] < 0:
            mutated_genotype["max_norm"] = 0.0001

        if mutated_genotype["epsilon_decay"] >= 1:
            mutated_genotype["epsilon_decay"] = 0.999
        if mutated_genotype["curiosity_decay"] >= 1:
            mutated_genotype["curiosity_decay"] = 0.999

        return mutated_genotype

    def make_phenotype(genotype):
        genome_config = config["genome"]
        phenotype = {}
        for name, value in genotype.items():
            if genome_config["genes"][name].get("type") == "int":
                value = round(value)    
            phenotype[name] = value
        return phenotype