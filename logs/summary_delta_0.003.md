# Benchmark delta_0.003

40 random oracles per family per experiment; the same oracle seeds are used in every experiment. Query saving is over correct tasks, relative to 60.

| experiment | noise (misfire, flip) | budget | accuracy | worst family | query saving | mean queries |
|---|---|---|---|---|---|---|
| ours | (0.04, 0.02) | 60 | 0.997 | 0.975 | 0.602 | 23.8 |
| ours_stress | (0.08, 0.04) | 60 | 0.988 | 0.950 | 0.473 | 31.7 |

## Per-family accuracy / mean queries

| experiment | constant | balanced | linear | grover | randfun | simon | simon2 | perm |
|---|---|---|---|---|---|---|---|---|
| ours | 1.00 / 31 | 1.00 / 26 | 1.00 / 5 | 1.00 / 23 | 0.97 / 22 | 1.00 / 30 | 1.00 / 23 | 1.00 / 31 |
| ours_stress | 1.00 / 32 | 0.97 / 36 | 1.00 / 6 | 0.95 / 30 | 0.97 / 30 | 1.00 / 43 | 1.00 / 31 | 1.00 / 47 |

## Confusion matrix (ours; rows = true family, columns = reported family; secret errors are not shown here)

| true \ reported | constant | balanced | linear | grover | randfun | simon | simon2 | perm | none |
|---|---|---|---|---|---|---|---|---|---|
| constant | 40 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| balanced | 0 | 40 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear | 0 | 0 | 40 | 0 | 0 | 0 | 0 | 0 | 0 |
| grover | 0 | 0 | 0 | 40 | 0 | 0 | 0 | 0 | 0 |
| randfun | 1 | 0 | 0 | 0 | 39 | 0 | 0 | 0 | 0 |
| simon | 0 | 0 | 0 | 0 | 0 | 40 | 0 | 0 | 0 |
| simon2 | 0 | 0 | 0 | 0 | 0 | 0 | 40 | 0 | 0 |
| perm | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 40 | 0 |

Failures in ours: 1

- randfun secret=None -> constant 1 (queries 5, seed 16365)

## Confusion matrix (ours_stress; rows = true family, columns = reported family; secret errors are not shown here)

| true \ reported | constant | balanced | linear | grover | randfun | simon | simon2 | perm | none |
|---|---|---|---|---|---|---|---|---|---|
| constant | 40 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| balanced | 0 | 39 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| linear | 0 | 0 | 40 | 0 | 0 | 0 | 0 | 0 | 0 |
| grover | 2 | 0 | 0 | 38 | 0 | 0 | 0 | 0 | 0 |
| randfun | 1 | 0 | 0 | 0 | 39 | 0 | 0 | 0 | 0 |
| simon | 0 | 0 | 0 | 0 | 0 | 40 | 0 | 0 | 0 |
| simon2 | 0 | 0 | 0 | 0 | 0 | 0 | 40 | 0 | 0 |
| perm | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 40 | 0 |

Failures in ours_stress: 4

- balanced secret=None -> randfun None (queries 16, seed 13381)
- grover secret=230 -> constant 0 (queries 60, seed 15362)
- grover secret=172 -> constant 0 (queries 60, seed 15384)
- randfun secret=None -> constant 1 (queries 5, seed 16365)
