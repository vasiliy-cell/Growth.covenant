"""
Genes, as the panel reads them back out of a log.

Two questions the panel answers about genes, and neither is a join the log
does for you: what the population carried at a given moment, and what one
agent's own line carried on its way down to it.
"""

import os

from src.persistence.log_reader import RunLogReader
from src.persistence.run_log import RunLog
from src.UI import reports


GENES = ["alpha", "sigma"]


def world(tmp_path, species="clons"):
    return RunLog(
        directory=os.path.join(tmp_path, "logs"),
        world_id=f"genes-{species}",
        run_id="r0",
        seed=1,
        episode_length=20,
        config={},
        species=species,
        gene_names=GENES,
    )


def born(log, step, index, parents, alpha, genotype=None):
    agent_id = f"a-{index:04d}"

    log.log_birth(
        step=step, agent_id=agent_id, index=index, parents=parents, energy=50.0,
        genotype=genotype if genotype is not None else {"alpha": alpha, "sigma": 0.005},
        phenotype={"alpha": alpha, "sigma": 0.005},
    )

    return agent_id


def window(log, step, agent_ids):
    # A per-agent window row is written for whoever took a step in it, which
    # in a real run is everybody alive.
    for agent_id in agent_ids:
        log.log_step(
            step=step, agent_id=agent_id, position=(1, 1), action=0,
            env_reward=1.0, intrinsic_reward=0.0, shaped_reward=1.0,
            energy=10.0, age=step,
        )

    log.end_episode(
        step=step,
        agents={
            agent_id: {"epsilon": 0.1, "curiosity_beta": 0.1, "energy": 10.0, "age": step}
            for agent_id in agent_ids
        },
        non_empty_ratio=0.3,
    )


def test_the_population_average_is_over_who_was_alive(tmp_path):
    log = world(tmp_path)

    founder = born(log, 0, 0, [], alpha=1.0)
    child = born(log, 10, 1, [founder], alpha=3.0)

    window(log, 20, [founder])              # one agent carrying 1.0
    window(log, 40, [founder, child])       # and now two, carrying 1.0 and 3.0
    log.close()

    reader = RunLogReader(log.path)
    answer = reports.genes(reader, ["alpha"])

    assert answer["genes"] == sorted(GENES)
    assert answer["series"]["alpha"] == [1.0, 2.0]
    assert answer["agents"] == [1, 2]


def test_a_lineage_is_a_chain_with_no_branches(tmp_path):
    log = world(tmp_path)

    founder = born(log, 0, 0, [], alpha=1.0)
    parent = born(log, 10, 1, [founder], alpha=2.0)
    born(log, 12, 2, [founder], alpha=9.0)          # a sibling of the parent
    child = born(log, 20, 3, [parent, founder], alpha=3.0)
    born(log, 22, 4, [child], alpha=4.0)            # a descendant, below the agent asked about

    window(log, 20, [founder, parent, child])
    log.close()

    line = reports.lineage(RunLogReader(log.path), child)["line"]

    # Founder first, the agent itself last, and nobody who is not an ancestor.
    assert [link["index"] for link in line] == [0, 1, 3]
    assert [link["generation"] for link in line] == [0, 1, 2]
    assert [link["phenotype"]["alpha"] for link in line] == [1.0, 2.0, 3.0]


def test_mendel_alleles_and_the_mutations_along_a_line(tmp_path):
    log = world(tmp_path, species="mendel")

    # [[value, dominance], [value, dominance]] - the shape mendel stores.
    founder_genes = {"alpha": [[1.0, "A"], [1.5, "a"]], "sigma": [[0.005, "A"], [0.005, "a"]]}
    # The child's first allele is one the founder held: nothing mutated.
    kept = {"alpha": [[1.0, "A"], [2.0, "a"]], "sigma": [[0.005, "A"], [0.005, "a"]]}
    # This one holds a value the parent never had: it mutated on the way down.
    mutant = {"alpha": [[7.7, "A"], [2.0, "a"]], "sigma": [[0.005, "a"], [0.005, "a"]]}

    founder = born(log, 0, 0, [], alpha=1.0, genotype=founder_genes)
    heir = born(log, 10, 1, [founder], alpha=1.0, genotype=kept)
    changed = born(log, 20, 2, [heir], alpha=7.7, genotype=mutant)

    window(log, 20, [founder, heir, changed])
    log.close()

    answer = reports.lineage(RunLogReader(log.path), changed)
    line = answer["line"]

    assert answer["species"] == "mendel"
    assert [link["index"] for link in line] == [0, 1, 2]

    # A founder was handed nothing, so nothing of it can have changed.
    assert line[0]["mutated"] == {}
    assert line[0]["alleles"]["alpha"] == [[1.0, "A"], [1.5, "a"]]

    assert line[1]["mutated"]["alpha"] is False
    assert line[2]["mutated"]["alpha"] is True
    assert line[2]["mutated"]["sigma"] is False


def test_a_genome_without_alleles_has_none_to_show(tmp_path):
    log = world(tmp_path)

    founder = born(log, 0, 0, [], alpha=1.0)
    child = born(log, 10, 1, [founder], alpha=2.0)
    window(log, 20, [founder, child])
    log.close()

    line = reports.lineage(RunLogReader(log.path), child)["line"]

    assert all(link["alleles"] == {} for link in line)
    assert all(link["mutated"] == {} for link in line)
