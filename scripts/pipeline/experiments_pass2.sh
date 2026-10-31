#!/usr/bin/env bash
# Pass 2 - direction two: "how should genes be passed on?"
#
# Plan changed (owner, after seeing cost/time on pass 1): direction 2 runs
# FIRST, on the GOOD baseline, with ALL 14 of direction 1's genes evolving
# at once - not "only the genes direction 1 found worth it", since
# direction 1 may never run. The bad-baseline leg follows once the owner
# sends concrete worsened gene means (research/.../bad_baseline.yml).
#
# ALL_GENES is direction 1's own 14-gene list (experiments_pass1.sh) minus
# alpha and sigma - sigma governs evolution itself (excluded there for
# exactly this reason, see the research draft's Limitations), and alpha
# only does anything inside non_linear's reproduce(); evolving it for
# clons/mendel would be inert noise, not a fair three-way comparison.
ALL_GENES="hidden_layers,hidden_size,gamma,learning_rate,target_update_freq,max_norm,buffer_size,batch_size,min_buffer_size,epsilon,epsilon_decay,epsilon_min,curiosity_beta,curiosity_decay"

# --- GOOD baseline leg: runnable now, config.yml untouched (same means as
# the already-completed baseline experiment - only --species/--set differ,
# exactly like every pass-1 experiment). ---
EXPERIMENTS_PASS2_GOOD=(
  "clons|clons|${ALL_GENES}|second research/clons"
  "non_linear|non_linear|${ALL_GENES}|second research/non_linear"
  "mendel|mendel|${ALL_GENES}|second research/mendel"
)

# --- BAD baseline leg: NOT ready. Needs research/.../bad_baseline.yml
# (owner's deliberately worsened gene means) before it can run - refusing
# to guess those numbers. Once that file exists, run_pass.sh --pass 2
# --leg bad swaps config.yml to it for this leg's whole duration. ---
EXPERIMENTS_PASS2_BAD=(
  "bad_baseline|clons||second research/bad/bad_baseline"
  "clons|clons|${ALL_GENES}|second research/bad/clons"
  "non_linear|non_linear|${ALL_GENES}|second research/bad/non_linear"
  "mendel|mendel|${ALL_GENES}|second research/bad/mendel"
)
