#!/usr/bin/env bash
# Pass 1 - direction one: "which gene groups are worth evolving at all?"
#
# Good baseline (every gene frozen) plus the 6 leave-one-in groups, compared
# only against the good baseline (see the research draft: this pass has no
# goal of beating it, just of seeing which groups are dead weight).
#
# One line per experiment: name|species|evolve_genes (comma-separated, empty
# for the baseline - every gene stays frozen at its mean). The grouping is
# the owner's, not a guess from config.yml's section comments:
#   1) network shape   - hidden_layers, hidden_size
#   2) gamma            - gamma, alone
#   3) optimizer        - learning_rate, target_update_freq, max_norm
#   4) memory           - buffer_size, batch_size, min_buffer_size
#   5) exploration      - epsilon, epsilon_decay, epsilon_min
#   6) curiosity        - curiosity_beta, curiosity_decay
#
# Every non-baseline group runs as non_linear (BLX-alpha), per the research
# design: leave-one-in is tested under sexual, non-clonal reproduction.

EXPERIMENTS_PASS1=(
  "good_baseline|clons|"
  "network_shape|non_linear|hidden_layers,hidden_size"
  "gamma|non_linear|gamma"
  "optimizer|non_linear|learning_rate,target_update_freq,max_norm"
  "memory|non_linear|buffer_size,batch_size,min_buffer_size"
  "exploration|non_linear|epsilon,epsilon_decay,epsilon_min"
  "curiosity|non_linear|curiosity_beta,curiosity_decay"
)
