# Benchmark final

50 random oracles per family per experiment; the same oracle seeds are used in every experiment. Query saving is over correct tasks, relative to 60.

| experiment | noise (misfire, flip) | budget | accuracy | worst family | query saving | mean queries |
|---|---|---|---|---|---|---|
| ours | (0.04, 0.02) | 60 | 0.998 | 0.980 | 0.591 | 24.5 |
| ours_stress | (0.08, 0.04) | 60 | 0.990 | 0.960 | 0.463 | 32.2 |
| ours_budget20 | (0.04, 0.02) | 20 | 0.917 | 0.680 | 0.726 | 16.7 |
| ours_budget30 | (0.04, 0.02) | 30 | 0.983 | 0.920 | 0.650 | 21.1 |
| ours_budget40 | (0.04, 0.02) | 40 | 0.993 | 0.960 | 0.620 | 22.8 |
| ours_budget50 | (0.04, 0.02) | 50 | 0.998 | 0.980 | 0.603 | 23.8 |
| no_readout_copies | (0.04, 0.02) | 60 | 1.000 | 1.000 | 0.486 | 30.9 |
| no_readout_copies_stress | (0.08, 0.04) | 60 | 0.960 | 0.860 | 0.400 | 36.9 |
| non_adaptive | (0.04, 0.02) | 60 | 0.970 | 0.900 | 0.000 | 60.0 |
| single_algorithm | (0.04, 0.02) | 60 | 0.752 | 0.000 | 0.326 | 45.3 |
| classical_only | (0.04, 0.02) | 60 | 0.680 | 0.160 | 0.232 | 50.5 |
| random_guess | (0.04, 0.02) | 60 | 0.113 | 0.000 | 1.000 | 0.0 |
| claude_reference | (0.04, 0.02) | 60 | 1.000 | 1.000 | 0.518 | 28.9 |
| claude_reference_stress | (0.08, 0.04) | 60 | 0.983 | 0.900 | 0.418 | 35.3 |

## Per-family accuracy / mean queries

| experiment | constant | balanced | linear | grover | randfun | simon | simon2 | perm |
|---|---|---|---|---|---|---|---|---|
| ours | 1.00 / 34 | 1.00 / 25 | 1.00 / 5 | 1.00 / 23 | 0.98 / 24 | 1.00 / 29 | 1.00 / 23 | 1.00 / 33 |
| ours_stress | 1.00 / 34 | 0.98 / 39 | 1.00 / 6 | 0.96 / 30 | 0.98 / 30 | 1.00 / 42 | 1.00 / 30 | 1.00 / 46 |
| ours_budget20 | 1.00 / 13 | 1.00 / 19 | 1.00 / 5 | 0.68 / 19 | 0.94 / 18 | 0.86 / 20 | 0.96 / 19 | 0.90 / 20 |
| ours_budget30 | 1.00 / 18 | 1.00 / 24 | 1.00 / 5 | 0.92 / 22 | 0.96 / 22 | 1.00 / 27 | 1.00 / 23 | 0.98 / 28 |
| ours_budget40 | 1.00 / 23 | 1.00 / 25 | 1.00 / 5 | 1.00 / 23 | 0.96 / 23 | 1.00 / 29 | 1.00 / 23 | 0.98 / 31 |
| ours_budget50 | 1.00 / 29 | 1.00 / 25 | 1.00 / 5 | 1.00 / 23 | 0.98 / 24 | 1.00 / 29 | 1.00 / 23 | 1.00 / 32 |
| no_readout_copies | 1.00 / 35 | 1.00 / 29 | 1.00 / 7 | 1.00 / 25 | 1.00 / 29 | 1.00 / 41 | 1.00 / 28 | 1.00 / 54 |
| no_readout_copies_stress | 0.98 / 36 | 1.00 / 39 | 1.00 / 8 | 0.86 / 34 | 1.00 / 32 | 0.92 / 50 | 0.96 / 42 | 0.96 / 56 |
| non_adaptive | 0.96 / 60 | 0.98 / 60 | 1.00 / 60 | 0.90 / 60 | 0.92 / 60 | 1.00 / 60 | 1.00 / 60 | 1.00 / 60 |
| single_algorithm | 0.52 / 60 | 1.00 / 57 | 0.56 / 60 | 0.00 / 60 | 0.94 / 40 | 1.00 / 29 | 1.00 / 23 | 1.00 / 33 |
| classical_only | 1.00 / 37 | 0.98 / 57 | 1.00 / 20 | 0.20 / 56 | 0.90 / 53 | 0.16 / 60 | 0.98 / 60 | 0.22 / 60 |
| random_guess | 0.12 / 0 | 0.28 / 0 | 0.00 / 0 | 0.00 / 0 | 0.12 / 0 | 0.00 / 0 | 0.00 / 0 | 0.38 / 0 |
| claude_reference | 1.00 / 35 | 1.00 / 33 | 1.00 / 6 | 1.00 / 28 | 1.00 / 25 | 1.00 / 36 | 1.00 / 30 | 1.00 / 39 |
| claude_reference_stress | 1.00 / 35 | 1.00 / 40 | 1.00 / 6 | 0.90 / 33 | 1.00 / 28 | 0.98 / 48 | 0.98 / 42 | 1.00 / 49 |

## Confusion matrix (ours; rows = true family, columns = reported family; secret errors are not shown here)

| true \ reported | constant | balanced | linear | grover | randfun | simon | simon2 | perm | none |
|---|---|---|---|---|---|---|---|---|---|
| constant | 50 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| balanced | 0 | 50 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear | 0 | 0 | 50 | 0 | 0 | 0 | 0 | 0 | 0 |
| grover | 0 | 0 | 0 | 50 | 0 | 0 | 0 | 0 | 0 |
| randfun | 1 | 0 | 0 | 0 | 49 | 0 | 0 | 0 | 0 |
| simon | 0 | 0 | 0 | 0 | 0 | 50 | 0 | 0 | 0 |
| simon2 | 0 | 0 | 0 | 0 | 0 | 0 | 50 | 0 | 0 |
| perm | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 50 | 0 |

Failures in ours: 1

- randfun secret=None -> constant 1 (queries 5, seed 16365)

## Confusion matrix (ours_stress; rows = true family, columns = reported family; secret errors are not shown here)

| true \ reported | constant | balanced | linear | grover | randfun | simon | simon2 | perm | none |
|---|---|---|---|---|---|---|---|---|---|
| constant | 50 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| balanced | 0 | 49 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| linear | 0 | 0 | 50 | 0 | 0 | 0 | 0 | 0 | 0 |
| grover | 2 | 0 | 0 | 48 | 0 | 0 | 0 | 0 | 0 |
| randfun | 1 | 0 | 0 | 0 | 49 | 0 | 0 | 0 | 0 |
| simon | 0 | 0 | 0 | 0 | 0 | 50 | 0 | 0 | 0 |
| simon2 | 0 | 0 | 0 | 0 | 0 | 0 | 50 | 0 | 0 |
| perm | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 50 | 0 |

Failures in ours_stress: 4

- balanced secret=None -> randfun None (queries 16, seed 13381)
- grover secret=172 -> constant 0 (queries 60, seed 15384)
- grover secret=120 -> constant 0 (queries 60, seed 15386)
- randfun secret=None -> constant 1 (queries 5, seed 16365)
