"""Random oracle instances for the eight families of the problem statement (section 3).

Every generator returns an Oracle with the truth table ``f`` (f[x] for x in 0..2^n-1),
the family name and the secret in the format the solver must report.
"""
from dataclasses import dataclass

import numpy as np

FAMILIES = ("constant", "balanced", "linear", "grover", "randfun", "simon", "simon2", "perm")
FAMILY_M = {"constant": 1, "balanced": 1, "linear": 1, "grover": 1, "randfun": 1,
            "simon": 8, "simon2": 8, "perm": 8}


@dataclass
class Oracle:
    family: str
    f: np.ndarray
    secret: object
    n: int = 8

    @property
    def m(self):
        return FAMILY_M[self.family]


def _parity(v):
    return bin(v).count("1") & 1


def constant(rng, n=8, c=None):
    c = int(rng.integers(2)) if c is None else c
    return Oracle("constant", np.full(2 ** n, c, dtype=np.int64), c, n)


def balanced(rng, n=8):
    N = 2 ** n
    f = np.zeros(N, dtype=np.int64)
    f[rng.choice(N, N // 2, replace=False)] = 1
    return Oracle("balanced", f, None, n)


def linear(rng, n=8, a=None, b=None):
    a = int(rng.integers(1, 2 ** n)) if a is None else a
    b = int(rng.integers(2)) if b is None else b
    f = np.array([_parity(a & x) ^ b for x in range(2 ** n)], dtype=np.int64)
    return Oracle("linear", f, [a, b], n)


def grover(rng, n=8, t=None):
    t = int(rng.integers(2 ** n)) if t is None else t
    f = np.zeros(2 ** n, dtype=np.int64)
    f[t] = 1
    return Oracle("grover", f, t, n)


def randfun(rng, n=8, p=0.3):
    f = (rng.random(2 ** n) < p).astype(np.int64)
    return Oracle("randfun", f, None, n)


def _coset_function(rng, n, subspace):
    """f constant on cosets of `subspace`, distinct (random labels) across cosets."""
    N = 2 ** n
    f = np.full(N, -1, dtype=np.int64)
    labels = rng.permutation(N)
    k = 0
    for x in range(N):
        if f[x] < 0:
            for h in subspace:
                f[x ^ h] = labels[k]
            k += 1
    return f


def simon(rng, n=8, s=None):
    s = int(rng.integers(1, 2 ** n)) if s is None else s
    return Oracle("simon", _coset_function(rng, n, (0, s)), s, n)


def simon2(rng, n=8, h1=None, h2=None):
    N = 2 ** n
    if h1 is None:
        h1 = int(rng.integers(1, N))
        h2 = int(rng.integers(1, N))
        while h2 == h1:
            h2 = int(rng.integers(1, N))
    H = (0, h1, h2, h1 ^ h2)
    return Oracle("simon2", _coset_function(rng, n, H), sorted(H[1:]), n)


def perm(rng, n=8):
    return Oracle("perm", rng.permutation(2 ** n).astype(np.int64), None, n)


GENERATORS = {"constant": constant, "balanced": balanced, "linear": linear, "grover": grover,
              "randfun": randfun, "simon": simon, "simon2": simon2, "perm": perm}


def random_oracle(family, rng, n=8):
    return GENERATORS[family](rng, n)


def reference_examples():
    """The public reference instances of section 4, built exactly as stated there."""
    N = 256
    s = 105
    H = (0, 15, 49, 62)
    return {
        "linear": Oracle("linear", np.array([_parity(178 & x) ^ 1 for x in range(N)]), [178, 1]),
        "simon": Oracle("simon", np.array([min(x, x ^ s) for x in range(N)]), 105),
        "simon2": Oracle("simon2", np.array([min(x ^ h for h in H) for x in range(N)]), [15, 49, 62]),
        "perm": Oracle("perm", np.array([(37 * x + 11) % 256 for x in range(N)]), None),
        "grover": Oracle("grover", np.array([int(x == 173) for x in range(N)]), 173),
        "constant": Oracle("constant", np.ones(N, dtype=np.int64), 1),
    }
