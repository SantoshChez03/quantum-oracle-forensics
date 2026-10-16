"""Claude's reference solver for Quantum Oracle Forensics (QryptoNox, Qiskit Fall Fest 2026).

    solve(n, m, budget, families, run) -> (family, secret)

Self-contained: imports only numpy and qiskit (section 6 limits).

Ideas
-----
1. Free redundant readout. Readout flips hit each measured bit independently,
   so CNOT-copying a qubit before measurement gives a second, independent read
   at zero query cost. Agreeing copies are almost never both wrong (p^2);
   disagreeing copies mark the bit as unknown instead of silently wrong.
   Every likelihood below works on these per-bit records exactly.
2. Bayesian sequential decisions. Every hypothesis gets an exact likelihood
   under the noise model; noise parameters are unknown to the solver, so all
   likelihoods are marginalised over {normal (4%, 2%), stress (8%, 4%)}.
   Each stage stops as soon as one answer has posterior >= 1 - EPS.

m = 8  (simon / simon2 / perm)  -- hidden subgroup problem over (Z_2^8, XOR)
   Fourier sampling (H, oracle, H; N&C fig. 5.5, eq. 5.77) gives y uniform over
   K-perp, K = {0}, {0,s} or a 2-dim subspace. Posterior over all 11 051
   hypotheses. Once one K leads, collision checks f(x) =? f(x^d), d in K, confirm it.

m = 1  (constant / balanced / linear / grover / randfun)
   Deutsch-Jozsa shots triage into
     A       constant | grover   (z = 0 almost surely)
     linear  z = a
     C       balanced | randfun  (z spread out)
   A      -> 6 classical probes, then adaptive Grover with a flag oracle call
   linear -> read b = f(0) with triple readout until decisive
   C      -> amplitude-amplified DJ (3 oracle calls): P(z=0) = sin^2(3 theta),
             sin(theta) = |1-2w|. Balanced stays at 0, randfun jumps to 0.6-1.
"""
import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Gate

N = 8
NOISE_GRID = ((0.04, 0.02), (0.08, 0.04))       # (misfire, readout flip)
LOG_NOISE_PRIOR = np.log(np.full(len(NOISE_GRID), 1 / len(NOISE_GRID)))

EPS_M8 = 1e-3          # m=8: stop when best hypothesis >= 1 - EPS
EPS_TRIAGE = 1e-3      # m=1: commit to A / linear / C
EPS_BAL_RAND = 1e-3    # m=1: commit to balanced / randfun
EPS_B = 1e-3           # linear: stop reading b
GROVER_K = 10          # Grover iterations per shot (optimum 12; 10 is noise-robust)
M8_FOURIER_FIRST = 12  # Fourier samples before collision checks start

_POP = np.array([bin(i).count("1") for i in range(256)])
_BITS = ((np.arange(256)[:, None] >> np.arange(N)) & 1).astype(bool)   # 256 x 8


def _lse(a, axis=None):
    a = np.asarray(a, dtype=float)
    mx = np.max(a, axis=axis, keepdims=True)
    out = mx + np.log(np.sum(np.exp(a - mx), axis=axis, keepdims=True))
    return np.squeeze(out, axis=axis) if axis is not None else float(out.squeeze())


# ----------------------------------------------------------------------------
# Budget accounting
# ----------------------------------------------------------------------------
class _OutOfBudget(Exception):
    pass


class _Budget:
    def __init__(self, run, limit):
        self._run, self.limit, self.used = run, limit, 0

    @property
    def left(self):
        return self.limit - self.used

    def keys(self, qc, shots):
        """Run and return one integer per shot (classical bit k = bit k)."""
        cost = sum(i.operation.name == "oracle" for i in qc.data) * shots
        if shots <= 0 or cost > self.left:
            raise _OutOfBudget()
        self.used += cost
        out = []
        for key, c in self._run(qc, shots).items():
            out += [int(key.replace(" ", ""), 2)] * int(c)
        return out


# ----------------------------------------------------------------------------
# Circuits (every oracle use is the judges' placeholder gate)
# ----------------------------------------------------------------------------
def _oracle(m):
    return Gate("oracle", N + m, [])


def _mcz_on_zero(qc, q):
    """Reflection I - 2|0><0| on qubits q."""
    qc.x(q)
    qc.h(q[-1])
    qc.mcx(q[:-1], q[-1])
    qc.h(q[-1])
    qc.x(q)


def _measure_with_copies(qc, data, copies, cl0=0):
    """CNOT each data qubit onto its copy, then measure data then copies."""
    for d, c in zip(data, copies):
        qc.cx(d, c)
    qc.measure(data, range(cl0, cl0 + len(data)))
    qc.measure(copies, range(cl0 + len(data), cl0 + len(data) + len(copies)))


def _classical_query(x):
    """f(x) for m=1, output read three times (q8 + copies q9, q10)."""
    qc = QuantumCircuit(N + 3, 3)
    for k in range(N):
        if (x >> k) & 1:
            qc.x(k)
    qc.append(_oracle(1), list(range(N + 1)))
    qc.cx(N, N + 1)
    qc.cx(N, N + 2)
    qc.measure([N, N + 1, N + 2], [0, 1, 2])
    return qc


def _dj(amplified=False):
    """DJ (1 call) or amplitude-amplified DJ A R A R A (3 calls), A = H O H.
    x on q0-7, |-> on q8, copies of x on q9-16. clbits 0-7 x, 8-15 copies."""
    X = list(range(N))
    qc = QuantumCircuit(2 * N + 1, 2 * N)
    qc.x(N)
    qc.h(N)
    rounds = 3 if amplified else 1
    for r in range(rounds):
        if r:
            _mcz_on_zero(qc, X)
        qc.h(X)
        qc.append(_oracle(1), X + [N])
        qc.h(X)
    _measure_with_copies(qc, X, list(range(N + 1, 2 * N + 1)))
    return qc


def _simon(group):
    """Fourier sampling for m=8 with 4 of the 8 x bits copied (20 qubits).
    group 0 copies bits 0-3, group 1 copies bits 4-7.
    clbits 0-7 x, 8-11 copies."""
    X = list(range(N))
    qc = QuantumCircuit(2 * N + 4, N + 4)
    qc.h(X)
    qc.append(_oracle(N), list(range(2 * N)))
    qc.h(X)
    src = X[4 * group: 4 * group + 4]
    for d, c in zip(src, range(2 * N, 2 * N + 4)):
        qc.cx(d, c)
    qc.measure(X, range(N))
    qc.measure(list(range(2 * N, 2 * N + 4)), range(N, N + 4))
    return qc


def _read_f8_circuit(x):
    qc = QuantumCircuit(2 * N, N)
    for k in range(N):
        if (x >> k) & 1:
            qc.x(k)
    qc.append(_oracle(N), list(range(2 * N)))
    qc.measure(range(N, 2 * N), range(N))
    return qc


def _grover_flag(k):
    """k Grover iterations + 1 flag call; x and flag copied by CNOT (19 qubits).
    clbits: 0-7 x, 8 flag, 9-16 x copy, 17 flag copy."""
    X, OUT, FLAG, XC, FC = list(range(8)), 8, 9, list(range(10, 18)), 18
    qc = QuantumCircuit(19, 18)
    qc.h(X)
    qc.x(OUT)
    qc.h(OUT)
    for _ in range(k):
        qc.append(_oracle(1), X + [OUT])
        qc.h(X)
        _mcz_on_zero(qc, X)
        qc.h(X)
    qc.append(_oracle(1), X + [FLAG])
    for a, b in zip(X, XC):
        qc.cx(a, b)
    qc.cx(FLAG, FC)
    qc.measure(X, range(8))
    qc.measure(FLAG, 8)
    qc.measure(XC, range(9, 17))
    qc.measure(FC, 17)
    return qc


# ----------------------------------------------------------------------------
# Per-bit readout records
# ----------------------------------------------------------------------------
def _bit_M(first, second, pf):
    """P(record | true bit = 0 / 1) for each bit, shape (..., 8, 2).
    second < 0 means the bit was read once."""
    first, second = np.asarray(first), np.asarray(second)
    M = np.empty(first.shape + (2,))
    for v in (0, 1):
        p1 = np.where(first == v, 1 - pf, pf)
        p2 = np.where(second == v, 1 - pf, pf)
        M[..., v] = np.where(second < 0, p1, p1 * p2)
    return M


def _records_full(keys):
    """DJ records: every bit duplicated."""
    k = np.asarray(keys)
    first = (k[:, None] >> np.arange(N)) & 1
    second = (k[:, None] >> (N + np.arange(N))) & 1
    return first, second


def _records_simon(keys, group):
    k = np.asarray(keys)
    first = (k[:, None] >> np.arange(N)) & 1
    second = -np.ones_like(first)
    second[:, 4 * group: 4 * group + 4] = (k[:, None] >> (N + np.arange(4))) & 1
    return first, second


def _zero_nonzero(M):
    """P(record | true y = 0) and P(record | true y uniform over 255 nonzero)."""
    P0 = np.prod(M[..., 0], axis=-1)
    Ptot = np.prod(M[..., 0] + M[..., 1], axis=-1)
    return P0, (Ptot - P0) / 255


# ----------------------------------------------------------------------------
# m = 8: Bayesian hidden-subgroup identification
# ----------------------------------------------------------------------------
_SUB2 = None


def _subspaces():
    """All 10 795 2-dim subspaces of Z_2^8 as sorted triples (h1 < h2 < h3)."""
    global _SUB2
    if _SUB2 is None:
        _SUB2 = np.array([(a, b, a ^ b) for a in range(1, 256)
                          for b in range(a + 1, 256) if (a ^ b) > b])
    return _SUB2


def _pair_rates(pm, pf):
    """Collision test: read f(x) and f(x^d) once each and compare.
    alpha = P(equal | d in K); beta = P(equal | d not in K), a conservative
    cap because structured oracles can put f(x), f(x^d) one bit apart."""
    S = ((1 - pf) ** 2 + pf ** 2) ** N
    alpha = ((1 - pm) ** 2 + pm ** 2) * S
    beta = 1.5 * pf + pm ** 2 * S
    return alpha, beta


def _m8_posterior(recs, pairs, fams):
    """recs: list of (first, second) record arrays. Walsh form of the
    likelihood (N&C eq. 5.77 convolved with per-bit readout records):
      P(rec | K) = (1-pm)/256 * sum_{k in K} prod_i T_i(k_i) + pm * prod_i M_i(0)
      T_i(0) = M_i(0) + M_i(1),  T_i(1) = M_i(0) - M_i(1)."""
    tri = _subspaces()
    size = {"perm": 1, "simon": 255, "simon2": len(tri)}
    member = {"perm": [np.zeros(1, bool) for _ in pairs],
              "simon": [np.arange(1, 256) == d for d, _ in pairs],
              "simon2": [(tri == d).any(axis=1) for d, _ in pairs]}
    first = np.concatenate([r[0] for r in recs]) if recs else None
    second = np.concatenate([r[1] for r in recs]) if recs else None
    per = {f: [] for f in fams}
    for (pm, pf), lpn in zip(NOISE_GRID, LOG_NOISE_PRIOR):
        ll = {f: np.zeros(size[f]) for f in fams}
        if recs:
            M = _bit_M(first, second, pf)                     # T x 8 x 2
            T0, T1 = M[..., 0] + M[..., 1], M[..., 0] - M[..., 1]
            G = np.prod(np.where(_BITS[:, None, :], T1[None], T0[None]), axis=2)
            P0 = np.prod(M[..., 0], axis=1)                   # misfire term
            c = (1 - pm) / 256
            for f in fams:
                if f == "perm":
                    P = c * G[0][None] + pm * P0
                elif f == "simon":
                    P = c * (G[0][None] + G[1:]) + pm * P0
                else:
                    P = c * (G[0][None] + G[tri[:, 0]] + G[tri[:, 1]]
                             + G[tri[:, 2]]) + pm * P0
                ll[f] += np.log(np.maximum(P, 1e-300)).sum(axis=1)
        alpha, beta = _pair_rates(pm, pf)
        for j, (d, eq) in enumerate(pairs):
            pin, pout = (alpha, beta) if eq else (1 - alpha, 1 - beta)
            for f in fams:
                ll[f] += np.where(member[f][j], np.log(pin), np.log(pout))
        for f in fams:
            per[f].append(lpn + ll[f])
    lp_fam = -np.log(len(fams))
    return {f: lp_fam - np.log(size[f]) + _lse(np.stack(per[f]), axis=0)
            for f in fams}


def _m8_decode(fam, i):
    if fam == "perm":
        return None
    if fam == "simon":
        return int(i) + 1
    return [int(v) for v in _subspaces()[i]]


def _solve_m8(b, families, seed=2026):
    fams = [f for f in ("simon", "simon2", "perm") if f in families] or \
           ["simon", "simon2", "perm"]
    rng = np.random.default_rng(seed)
    recs, pairs, checks, matched = [], [], {}, set()
    n_four, group, best = 0, 0, ("perm", None)
    while b.left > 0:
        # collision checks only for elements of the leading K not yet matched;
        # Fourier samples do everything else (incl. simon(s) vs subspaces ∋ s)
        todo = []
        if n_four >= M8_FOURIER_FIRST and best[0] != "perm" and b.left >= 2:
            K = [best[1]] if best[0] == "simon" else best[1][:2]
            todo = [d for d in K if d not in matched and checks.get(d, 0) < 3]
        if todo:
            d = todo[0]
            checks[d] = checks.get(d, 0) + 1
            x = int(rng.integers(256))
            r1 = b.keys(_read_f8_circuit(x), 1)[0]
            r2 = b.keys(_read_f8_circuit(x ^ d), 1)[0]
            pairs.append((d, r1 == r2))
            if r1 == r2:
                matched.add(d)
        else:
            shots = min(8 if n_four == 0 else 4, b.left)
            recs.append(_records_simon(b.keys(_simon(group), shots), group))
            n_four += shots
            group ^= 1
        post = _m8_posterior(recs, pairs, fams)
        total = _lse(np.concatenate(list(post.values())))
        f_best = max(post, key=lambda f: post[f].max())
        i_best = int(np.argmax(post[f_best]))
        best = (f_best, _m8_decode(f_best, i_best))
        if np.exp(post[f_best][i_best] - total) >= 1 - EPS_M8:
            break
    return best


# ----------------------------------------------------------------------------
# m = 1
# ----------------------------------------------------------------------------
_RAND = None


def _randfun_prior():
    """(a values, log prior) for a = 1 - 2w, w = Binomial(256, 0.3)/256."""
    global _RAND
    if _RAND is None:
        from math import lgamma, log
        k = np.arange(257)
        lp = np.array([lgamma(257) - lgamma(i + 1) - lgamma(257 - i)
                       + i * log(0.3) + (256 - i) * log(0.7) for i in k])
        keep = lp > lp.max() - 30
        _RAND = (1 - 2 * k[keep] / 256, lp[keep] - _lse(lp[keep]))
    return _RAND


def _p0_amplified(a, pm):
    """P(true outcome 0) for A R A R A |0> with misfires (A -> I), a = <0|A|0>.
    Derived from A^2 = I, R = I - 2|0><0|; checked against brute force."""
    a2 = a * a
    none = (a * (3 - 4 * a2)) ** 2
    one = (1 - 2 * a2) ** 2 + 1 + (1 - 2 * a2) ** 2
    return ((1 - pm) ** 3 * none + pm * (1 - pm) ** 2 * one
            + pm ** 2 * (1 - pm) * 3 * a2 + pm ** 3)


def _m1_loglik(dj_recs, amp_recs):
    """Noise-marginalised log-likelihoods for 'A', 'linear' (array, a=1..255),
    'balanced', 'randfun'."""
    a_r, lp_r = _randfun_prior()
    q_A = 1 - 0.5 * 255 * 4 / 65536            # constant/grover mix at z = 0
    out = {k: [] for k in ("A", "linear", "balanced", "randfun")}
    for (pm, pf), lpn in zip(NOISE_GRID, LOG_NOISE_PRIOR):
        ll = {"A": 0.0, "linear": np.zeros(255), "balanced": 0.0,
              "randfun": np.zeros(len(a_r))}
        if dj_recs is not None:
            M = _bit_M(*dj_recs, pf)                        # T x 8 x 2
            P0, Pnz = _zero_nonzero(M)

            def spread(q):
                q = np.atleast_1d(q)[:, None]
                return (1 - pm) * (q * P0 + (1 - q) * Pnz) + pm * P0

            ll["A"] += np.log(spread(q_A)).sum()
            ll["balanced"] += np.log(spread(0.0)).sum()
            ll["randfun"] += np.log(spread(a_r ** 2)).sum(axis=1)
            Pa = np.prod(np.where(_BITS[1:, None, :], M[None, ..., 1],
                                  M[None, ..., 0]), axis=2)  # 255 x T
            ll["linear"] += np.log((1 - pm) * Pa + pm * P0).sum(axis=1)
        if amp_recs is not None:
            P0, Pnz = _zero_nonzero(_bit_M(*amp_recs, pf))
            for key, a in (("balanced", np.zeros(1)), ("randfun", a_r)):
                z = _p0_amplified(a, pm)[:, None]
                ll[key] = ll[key] + np.log(z * P0 + (1 - z) * Pnz).sum(axis=1)
        ll["balanced"] = float(np.squeeze(ll["balanced"]))
        ll["randfun"] = _lse(lp_r + ll["randfun"])
        for k in out:
            out[k].append(lpn + ll[k])
    return {k: _lse(np.stack(v), axis=0) for k, v in out.items()}


def _m1_posterior(dj_recs, amp_recs=None):
    ll = _m1_loglik(dj_recs, amp_recs)
    post = {"A": ll["A"] + np.log(2 / 5),           # constant + grover
            "linear": ll["linear"] + np.log(1 / 5) - np.log(255),
            "balanced": ll["balanced"] + np.log(1 / 5),
            "randfun": ll["randfun"] + np.log(1 / 5)}
    total = _lse(np.concatenate([np.atleast_1d(v) for v in post.values()]))
    return {k: np.exp(v - total) for k, v in post.items()}


def _cat(recs):
    return (np.concatenate([r[0] for r in recs]),
            np.concatenate([r[1] for r in recs])) if recs else None


def _read_triple(b, x):
    """One query, output bit read three times -> (r1, r2, r3)."""
    v = b.keys(_classical_query(x), 1)[0]
    return v & 1, (v >> 1) & 1, (v >> 2) & 1


def _read_f(b, x):
    return int(sum(_read_triple(b, x)) >= 2)


def _read_b(b):
    """b = f(0) for linear f. A misfire leaves the output at 0, so
    P(rec | b) = (1-pm) prod P(r_i | b) + pm prod P(r_i | 0)."""
    lp = np.zeros(2)
    while b.left > 0:
        r = np.array(_read_triple(b, 0))
        terms = []
        for (pm, pf), lpn in zip(NOISE_GRID, LOG_NOISE_PRIOR):
            pr = lambda v: np.prod(np.where(r == v, 1 - pf, pf))
            terms.append(lpn + np.log([pr(0), (1 - pm) * pr(1) + pm * pr(0)]))
        lp = lp + _lse(np.stack(terms), axis=0)
        if np.exp(lp - _lse(lp)).max() >= 1 - EPS_B:
            break
    return int(np.argmax(lp))


def _solve_A(b, k=GROVER_K):
    """constant(0) / constant(1) / grover (tested in branch_grover.py)."""
    reads = {}
    for x in range(6):
        if b.left < 1:
            break
        reads[x] = _read_f(b, x)
    if sum(reads.values()) >= 3:
        return "constant", 1
    for x, r in reads.items():
        if r == 1 and b.left >= 2:
            if _read_f(b, x) + _read_f(b, x) == 2:
                return "grover", x
    while b.left >= 5:
        kk = min(k, b.left - 1)
        v = b.keys(_grover_flag(kk), 1)[0]
        x, f1, xc, f2 = v & 0xFF, (v >> 8) & 1, (v >> 9) & 0xFF, (v >> 17) & 1
        if f1 and f2:
            if x == xc:
                return "grover", x
            if bin(x ^ xc).count("1") == 1 and b.left >= 1:
                return "grover", x if _read_f(b, x) else xc
        elif (f1 or f2) and x == xc and b.left >= 1:
            if _read_f(b, x):
                return "grover", x
    return "constant", 0


def _solve_m1(b):
    dj, amp = [], []
    stage = "triage"
    while b.left > 0:
        if stage == "triage":
            dj.append(_records_full(b.keys(_dj(), min(4 if not dj else 2, b.left))))
        else:
            if b.left < 3:
                break
            amp.append(_records_full(b.keys(_dj(amplified=True), 1)))
        p = _m1_posterior(_cat(dj), _cat(amp))
        a_best = int(np.argmax(p["linear"])) + 1
        lin = p["linear"].max()
        if stage == "triage":
            if p["A"] >= 1 - EPS_TRIAGE or (p["A"] > 0.5 and b.left <= 44):
                return _solve_A(b)
            if lin >= 1 - EPS_TRIAGE or (lin > 0.5 and b.left <= 4):
                return "linear", [a_best, _read_b(b) if b.left else 0]
            if p["balanced"] + p["randfun"] >= 1 - EPS_TRIAGE:
                stage = "balrand"
        if stage == "balrand":
            # amplified shots only enter the balanced / randfun likelihoods,
            # so from here on compare those two alone
            pb = p["balanced"] / (p["balanced"] + p["randfun"])
            if max(pb, 1 - pb) >= 1 - EPS_BAL_RAND:
                break
    if stage == "balrand":
        return ("balanced" if pb >= 0.5 else "randfun"), None
    if p["A"] >= max(lin, p["balanced"], p["randfun"]):
        return "constant", 0
    if lin >= max(p["balanced"], p["randfun"]):
        return "linear", [a_best, 0]
    return ("balanced" if p["balanced"] >= p["randfun"] else "randfun"), None


# ----------------------------------------------------------------------------
def solve(n, m, budget, families, run):
    b = _Budget(run, budget)
    try:
        if m == N:
            return _solve_m8(b, families)
        return _solve_m1(b)
    except _OutOfBudget:
        return "balanced", None        # unreachable in normal operation
