# Benchmark delta_0.001

40 random oracles per family per experiment; the same oracle seeds are used in every experiment. Query saving is over correct tasks, relative to 60.

| experiment | noise (misfire, flip) | budget | accuracy | worst family | query saving | mean queries |
|---|---|---|---|---|---|---|
| ours | (0.04, 0.02) | 60 | 0.997 | 0.975 | 0.560 | 26.4 |
| ours_stress | (0.08, 0.04) | 60 | 0.988 | 0.950 | 0.422 | 34.8 |

## Per-family accuracy / mean queries

| experiment | constant | balanced | linear | grover | randfun | simon | simon2 | perm |
|---|---|---|---|---|---|---|---|---|
| ours | 1.00 / 32 | 1.00 / 30 | 1.00 / 6 | 1.00 / 24 | 0.97 / 26 | 1.00 / 33 | 1.00 / 25 | 1.00 / 35 |
| ours_stress | 1.00 / 32 | 0.97 / 42 | 1.00 / 6 | 0.95 / 31 | 0.97 / 36 | 1.00 / 45 | 1.00 / 34 | 1.00 / 52 |

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

- randfun secret=None -> constant 1 (queries 6, seed 16365)

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

- balanced secret=None -> randfun None (queries 60, seed 13381)
- grover secret=230 -> constant 0 (queries 60, seed 15362)
- grover secret=172 -> constant 0 (queries 60, seed 15384)
- randfun secret=None -> constant 1 (queries 6, seed 16365)
