#!/usr/bin/env bash
# A SECOND, independent batch of 30 seeds - added because the first 15
# gave too much noise/variance per species to say anything about which
# reproduction type learns faster under the bad baseline. None of these
# overlap the original 15 in seeds.sh.
#
# Generated once with numpy.random.default_rng(20261109) (the date this
# batch was drawn, as the meta-seed) and frozen here - that file is the
# source of truth, same convention as seeds.sh.
#
# Split in half for parallel wall-clock, not for any experimental reason:
# SERVER_SEEDS ran on the rented box, MAC_SEEDS on the owner's machine.

SERVER_SEEDS=(
  1551805766
  670202583
  1040176728
  1634495950
  1537488854
  2135414605
  908190725
  828443656
  1190988665
  1708432993
  701897230
  1706578473
  1996669074
  1891633362
  1633811275
)

MAC_SEEDS=(
  1469168592
  2011396667
  675705288
  1619252817
  999047946
  64713326
  119331123
  1858319785
  1036090771
  863076076
  1891544534
  1482009083
  1479639638
  129324135
  1791642866
)

# A THIRD batch of 15, queued to run right after the 30 above finish (same
# machine, same bad genes, same probe) - the 30 were expected to leave only
# ~10 seeds that survive in all three species, too few; this widens the
# common-survivor pool further. Generated with a distinct meta-seed so it
# never collides with the 15 original or the 30 above.
EXTRA_SEEDS=(
  1278549092
  1875054694
  1875769966
  510294881
  111198889
  278906185
  2045177547
  1541155865
  1033668013
  40248644
  1603734309
  549906994
  1094375482
  1612522546
  2003317259
)

# A FOURTH batch of 10, queued right after EXTRA_SEEDS above - same bad
# genes, same probe, same rules. Widens the pool further.
SECOND_EXTRA_SEEDS=(
  1672802596
  611563536
  1107032872
  1842464693
  1310630172
  1200031674
  1111184216
  1587353058
  1974994958
  424772428
)

# A FIFTH batch of 30 - clons/mendel ONLY (owner explicitly skipped
# non_linear for this one; it already has plenty of data). Widens the
# clons-vs-mendel comparison specifically.
THIRD_BATCH_SEEDS=(
  1656982212
  1344494084
  1769747038
  305196229
  477670760
  1369528673
  139961480
  1126652752
  1143136312
  1520125360
  1793918713
  1313357300
  650643595
  1894404184
  2085674882
  554097749
  1003085197
  1466525455
  92555035
  357697139
  393842989
  465619781
  1725194726
  72061729
  248674815
  581462584
  1616709634
  707728676
  193016383
  1327050699
)
