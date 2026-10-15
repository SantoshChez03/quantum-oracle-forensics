# Benchmark delta_0.01

40 random oracles per family per experiment; the same oracle seeds are used in every experiment. Query saving is over correct tasks, relative to 60.

| experiment | noise (misfire, flip) | budget | accuracy | worst family | query saving | mean queries |
|---|---|---|---|---|---|---|
| ours | (0.04, 0.02) | 60 | 0.991 | 0.925 | 0.642 | 21.4 |
| ours_stress | (0.08, 0.04) | 60 | 0.981 | 0.950 | 0.528 | 28.3 |

## Per-family accuracy / mean queries

| experiment | constant | balanced | linear | grover | randfun | simon | simon2 | perm |
|---|---|---|---|---|---|---|---|---|
| ours | 1.00 / 31 | 1.00 / 21 | 1.00 / 4 | 1.00 / 22 | 0.93 / 18 | 1.00 / 26 | 1.00 / 21 | 1.00 / 27 |
| ours_stress | 1.00 / 31 | 0.97 / 30 | 0.97 / 5 | 0.95 / 29 | 0.95 / 24 | 1.00 / 40 | 1.00 / 28 | 1.00 / 40 |

## Confusion matrix (ours; rows = true family, columns = reported family; secret errors are not shown here)

| true \ reported | constant | balanced | linear | grover | randfun | simon | simon2 | perm | none |
|---|---|---|---|---|---|---|---|---|---|
| constant | 40 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| balanced | 0 | 40 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| linear | 0 | 0 | 40 | 0 | 0 | 0 | 0 | 0 | 0 |
| grover | 0 | 0 | 0 | 40 | 0 | 0 | 0 | 0 | 0 |
| randfun | 1 | 0 | 1 | 1 | 37 | 0 | 0 | 0 | 0 |
| simon | 0 | 0 | 0 | 0 | 0 | 40 | 0 | 0 | 0 |
| simon2 | 0 | 0 | 0 | 0 | 0 | 0 | 40 | 0 | 0 |
| perm | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 40 | 0 |

Failures in ours: 3

- randfun secret=None -> grover 6 (queries 16, seed 16345)
- randfun secret=None -> linear [229, 0] (queries 4, seed 16350)
- randfun secret=None -> constant 1 (queries 5, seed 16365)

## Confusion matrix (ours_stress; rows = true family, columns = reported family; secret errors are not shown here)

| true \ reported | constant | balanced | linear | grover | randfun | simon | simon2 | perm | none |
|---|---|---|---|---|---|---|---|---|---|
| constant | 40 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| balanced | 0 | 39 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| linear | 0 | 0 | 40 | 0 | 0 | 0 | 0 | 0 | 0 |
| grover | 2 | 0 | 0 | 38 | 0 | 0 | 0 | 0 | 0 |
| randfun | 1 | 0 | 0 | 1 | 38 | 0 | 0 | 0 | 0 |
| simon | 0 | 0 | 0 | 0 | 0 | 40 | 0 | 0 | 0 |
| simon2 | 0 | 0 | 0 | 0 | 0 | 0 | 40 | 0 | 0 |
| perm | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 40 | 0 |

Failures in ours_stress: 6

- balanced secret=None -> randfun None (queries 12, seed 13381)
- linear secret=[155, 1] -> linear [155, 0] (queries 6, seed 14352)
- grover secret=230 -> constant 0 (queries 60, seed 15362)
- grover secret=172 -> constant 0 (queries 60, seed 15384)
- randfun secret=None -> grover 6 (queries 16, seed 16345)
- randfun secret=None -> constant 1 (queries 5, seed 16365)
