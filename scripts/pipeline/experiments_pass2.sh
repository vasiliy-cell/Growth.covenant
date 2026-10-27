#!/usr/bin/env bash
# Pass 2 - direction two: "how should genes be passed on?" NOT READY YET.
#
# This file is a skeleton, not a runnable experiment matrix. Two things are
# still missing and MUST come from the owner before pass 2 can start - this
# project's rule is "ask before choosing any value that affects the
# experiment", and both of the gaps below are exactly that:
#
#   1. research/.../bad_baseline.yml does not exist yet. "bad baseline"
#      means specific gene MEANS deliberately worsened from good_baseline.yml
#      - which genes, and to what values, is an experiment design choice,
#      not something to guess here. Once the owner gives concrete numbers,
#      clone good_baseline.yml into bad_baseline.yml with just those means
#      changed (same structure, same scales/types).
#
#   2. The "genes that showed themselves worth evolving" are whatever pass 1
#      (experiments_pass1.sh) actually found - unknown until those 15 seeds
#      x 7 experiments are run and read. Fill WINNING_GENES below from that
#      result, not from a guess.
#
# Unlike pass 1 (same config.yml for every experiment, only --species and
# --set genome.evolve differ), pass 2 needs a DIFFERENT set of gene means
# (the bad baseline's), which --set cannot carry cleanly for a dozen genes
# at once. The intended mechanism is: copy bad_baseline.yml over config.yml
# before running this whole pass (pipeline.sh does this, and prints a clear
# warning before it overwrites the live file) - ask the owner to confirm
# this is the right mechanism (vs. e.g. adding a --config flag to run.py)
# before relying on it for a real run.

WINNING_GENES=""   # e.g. "gamma,epsilon,epsilon_decay" - fill in after pass 1

EXPERIMENTS_PASS2=(
  "bad_baseline|clons|"
  # "clons_evolve|clons|${WINNING_GENES}"
  # "non_linear_evolve|non_linear|${WINNING_GENES}"
  # "mendel_evolve|mendel|${WINNING_GENES}"
)
