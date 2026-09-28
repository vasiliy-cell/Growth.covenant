# The genome

Code: `src/Genome/`, `create_agents` / `make_phenotype` / `_reproduce` in
`src/environment/env.py`.

Weights are **not** inherited. A genome carries the recipe of a mind (how
it learns), and every agent learns its own weights from scratch during its
life. What passes between generations is the set of numbers below.

## Genotype and phenotype

- **genotype** - the DNA, what an agent passes on. For `clons` and
  `non_linear` it is `{gene: float}`. For `mendel` it is two alleles per
  gene, each with a dominance letter:
  `{gene: [[value, "A" | "a"], [value, "A" | "a"]]}`.
- **phenotype** - what the genotype was read into for this body:
  `{gene: number}`, with `int` genes rounded. The mind is built from it.

Both live in the `Genepool`. The phenotype is read **once** per agent and
cached, because reading a `mendel` genotype can involve a coin toss, and
reading it again could give a different body than the one whose weights
were saved. Checkpoints store both.

## The genes

Defined in `genome.genes` of `config.yml`. Each has `mean` (centre of the
first generation's draw), `scale` (its standard deviation) and `type`
(`float` or `int`). An optional `step` key is described in config.md but
no gene sets it and the code does not read it.

| gene | mean | scale | type | used for |
|---|---|---|---|---|
| `alpha` | 0.5 | 0.5 | float | non_linear: how far outside the parents a child may fall |
| `sigma` | 0.005 | 0.001 | float | per-gene mutation probability |
| `learning_rate` | 0.001 | 0.0005 | float | Adam lr |
| `max_norm` | 0.01 | 0.005 | float | gradient clip |
| `gamma` | 0.99 | 0.001 | float | discount |
| `target_update_freq` | 1000 | 200 | int | updates between target syncs |
| `hidden_size` | 64 | 8 | int | layer width |
| `hidden_layers` | 2 | 0.5 | int | number of hidden layers |
| `buffer_size` | 10000 | 2000 | int | replay capacity |
| `batch_size` | 32 | 4 | int | batch |
| `min_buffer_size` | 500 | 100 | int | warm-up before learning |
| `epsilon` | 0.7 | 0.1 | float | starting exploration |
| `epsilon_decay` | 0.995 | 0.002 | float | per-window epsilon factor |
| `epsilon_min` | 0.05 | 0.005 | float | exploration floor |
| `curiosity_beta` | 1.0 | 0.5 | float | curiosity strength |
| `curiosity_decay` | 0.995 | 0.002 | float | per-window beta factor |

(Values as in `config.yml` at the time of writing.)

Example: `hidden_layers` drawn from N(2, 0.5) and rounded gives 2 hidden
layers about 68% of the time, 1 or 3 about 16% each, and 0 (a single
linear layer) or 4 about 0.1% each.

## Frozen and evolving genes (`genome.evolve`)

`genome.evolve` lists the genes that vary. Every gene **not** listed is
frozen:

- every founder carries exactly its `mean`,
- mutation never changes it,
- in `non_linear` both parents hold the same value, so the blend returns
  it unchanged,
- in `mendel` both alleles hold the mean; dominance letters are drawn at
  genesis but never flipped.

A frozen gene still **takes its random draws and throws them away**, so
the `genome` stream is consumed the same way whatever is frozen. Under one
seed, two conditions that differ only in `evolve` give every evolving gene
the same numbers.

With `evolve: []` every agent carries the same genes. Currently all 16
genes are listed.

A name in `evolve` that is not a gene stops the run with an error. The
list belongs to the world: a continued world uses the list saved in its
checkpoint (a checkpoint from before the list existed evolves every gene),
whatever `config.yml` says now.

## Founders (first genome)

`reuse.make_first_genome`, with the `numpy:genome` stream, for each gene in
config order: one draw from `N(mean, scale)`; kept if the gene evolves,
replaced by `mean` if not. Then the safety clamps (below).

`mendel` does this **twice** (two full drafts, one per allele), then draws
a dominance letter `"A"` or `"a"` for every gene of the first draft, then
for every gene of the second.

## Mutation

`reuse.mutate` (clons, non_linear), for each gene of the child:

1. draw `u ~ U(0, 1)`; if `u < sigma` (the child's own `sigma` gene before
   mutation):
2. draw `factor ~ U(0.5, 2.0)` and, if the gene evolves, multiply it by
   `factor`,
3. after all genes, apply the safety clamps.

So each gene mutates with probability `sigma`, by a **factor**, which
means the same thing for a learning rate of 0.001 and a buffer of 10000.
With 16 genes and `sigma = 0.005`, about 92% of children are exact
copies. A positive factor never changes a gene's sign.

`mendel` mutation, per gene:

1. `sigma` is read from one allele of the child, chosen at random,
2. with probability `sigma`: pick one allele at random and multiply its
   value by `U(0.5, 2.0)` (if the gene evolves),
3. independently, with probability `sigma`: pick one allele at random and
   flip its dominance letter `A <-> a` (if the gene evolves),
4. clamps on both alleles.

### Safety clamps

Applied after the first draw and after every mutation, because values
outside these ranges break learning outright:

| gene | rule |
|---|---|
| `gamma` | `<= 0` → 0.001, `>= 1` → 0.999 |
| `learning_rate` | `< 0` → 0.0001 |
| `max_norm` | `< 0` → 0.0001 |
| `sigma` | `< 0` → 0.01 |
| `alpha` | `< 0` → 0.001 |
| `epsilon_decay` | `>= 1` → 0.999 |
| `curiosity_decay` | `>= 1` → 0.999 |

No other gene is clamped. For example, `curiosity_beta` drawn from
N(1.0, 0.5) is negative for about 2% of founders, which makes novelty a
penalty for them; `epsilon` or `epsilon_min` could in principle go
negative too.

## The three species

Chosen once per run (`genome.type`, or the terminal prompt, or
`--species`). A checkpoint refuses to be continued as another species.

### `clons` - asexual

- one parent, `partners_required = 0`,
- child genome = `mutate(parent genome)`,
- phenotype = genotype with `int` genes rounded.

### `non_linear` - sexual, BLX-alpha blend

- two parents (see pairing in [life.md](life.md#sexual-non_linear-mendel)),
- `alpha` is taken from the **mother** (first of the pair),
- for every gene: `lo = min(mother, father)`, `hi = max(...)`,
  `d = hi - lo`, child value `~ U(lo - alpha*d, hi + alpha*d)`,
- then `mutate(child)`,
- phenotype = genotype with `int` genes rounded.

With `alpha = 0` a child lies between its parents; with `alpha = 0.5`
the interval is twice as wide as the gap between them. A gene equal in
both parents is passed on unchanged (the draw is still taken).

### `mendel` - sexual, two alleles with dominance

- genotype: two alleles per gene, each `[value, "A" | "a"]`,
- **inheritance**: the child starts as a copy of the mother; then for each
  gene and for each allele slot `i` (0 and 1) separately, slot `i` is
  taken from the mother's slot `i` or the father's slot `i` with
  probability 0.5 each. (So a child can receive both alleles of a gene
  from the same parent.)
- then the mendel mutation above,
- **phenotype** (read once, with the agent's own
  `numpy:agent/<index>/phenotype` stream):
  - one `"A"` and one `"a"` → the value of the `"A"` allele (dominant),
  - `"AA"` or `"aa"` → one of the two alleles at random,
  - `int` genes rounded.

## Where genes appear in the logs

- `events/births` - one row per birth (founders included) with
  `genotype_json` (the whole genotype as JSON) and one `phen_<gene>`
  column per gene (float32).
- `events/deaths` - `genotype_json` of the agent that died.
- `run.json` - the species and the gene list.
