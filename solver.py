"""Quantum Oracle Forensics solver (IBM Qiskit Fall Fest 2026, QC@IITI x QryptoNox).

solve(n, m, budget, families, run) -> (family, secret)

Strategy
--------
Exact Bayesian inference over every (family, secret) hypothesis allowed by m, with the
section-3 noise model inside the likelihoods; adaptive experiment design (run the circuit
with the highest expected information gain per query); sequential stopping (answer as soon
as the top answer has posterior >= 1 - DELTA, or when the budget is spent).

* Noise level is not assumed: every hypothesis is paired with the nominal (4% misfire, 2%
  readout) and the doubled (8%, 4%) setting, and the posterior marginalises over both.
* Readout repetition: spare qubits receive CNOT copies of measured qubits right before
  measurement.  Readout flips are independent per measured bit, so two agreeing copies are
  almost surely right and a disagreement turns a silent error into a known erasure.  Costs
  no queries; it only uses qubits below the 20-qubit cap.

m = 8  (simon / simon2 / perm): Simon sampling circuit H-U-H; the measured z is uniform on
       the annihilator of the hidden subspace.  The likelihood has a closed form through the
       Walsh transform of the per-bit readout likelihoods, so all 1 + 255 + 10795 hypotheses
       are scored exactly after every shot.
m = 1  (constant / balanced / linear / grover / randfun): a menu of circuits
         G(j, H): phase oracle, j Grover iterations, Hadamard-basis readout
                  (j = 1 is Deutsch-Jozsa / Bernstein-Vazirani; even j is an "echo" that
                  returns a balanced function exactly to z = 0 but not a randfun),
         G(j, Z): j Grover iterations, computational readout (search for the marked input),
         C(x, y0): classical query of f(x), answer qubit initialised to y0 (alternated so a
                  misfire, which leaves y0 unchanged, does not bias the bit).
       Outcome probabilities come from an exact two-level (marked / unmarked) density-matrix
       model including misfires: exact for constant, linear and grover; exact in P(z = 0)
       for balanced / randfun with the other outcomes taken as uniform.
"""
import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Gate
from scipy.stats import binom

NOISE_LEVELS = ((0.04, 0.02), (0.08, 0.04))   # (oracle misfire, readout flip)
NOISE_PRIOR = (0.5, 0.5)
DELTA = 0.003           # stop when the top answer has posterior >= 1 - DELTA (swept: logs/summary_delta_*.md)
FLOOR = 2e-3            # weight of a uniform outcome mixed into every likelihood (robustness)
RANDFUN_P = 0.3
ECHO_JS = (1, 2, 4)
SEARCH_JS = (6, 8, 10, 12)
MAX_QUBITS = 20
SEED = 2026             # solver's own randomness (choice of classical-query inputs) is fixed,
                        # so a run is reproducible whenever run() itself is seeded

M1_FAMILIES = ("constant", "linear", "grover", "balanced", "randfun")
M8_FAMILIES = ("simon", "simon2", "perm")


# ----------------------------------------------------------------------------- helpers
def _popcount(n):
    return np.array([bin(i).count("1") for i in range(2 ** n)], dtype=np.int64)


def _bits_table(n):
    """B[z, k] = bit k of z."""
    z = np.arange(2 ** n)
    return (z[:, None] >> np.arange(n)[None, :]) & 1


def _readout_kernel(n, eps):
    """K[o, z] = P(observe o | true z) for independent bit flips (used for design only)."""
    pop = _popcount(n)
    N = 2 ** n
    d = pop[np.arange(N)[:, None] ^ np.arange(N)[None, :]]
    return eps ** d * (1 - eps) ** (n - d)


def _design_eps(eps, copies):
    """Binary-symmetric error rate with the same capacity as `copies` noisy readings of a bit.
    Only used to score candidate experiments; updates use the exact per-bit likelihoods."""
    if copies == 1:
        return eps
    # mutual information of the repetition channel with a uniform input bit
    # (the number of readings equal to 1 is a sufficient statistic)
    info = 0.0
    for k in range(copies + 1):
        pk0 = binom.pmf(k, copies, eps)
        pk1 = binom.pmf(copies - k, copies, eps)
        mix = 0.5 * (pk0 + pk1)
        for p in (pk0, pk1):
            if p > 0:
                info += 0.5 * p * np.log2(p / mix)
    target = 1 - info
    lo, hi = 1e-9, 0.5
    for _ in range(60):
        mid = (lo + hi) / 2
        h = -mid * np.log2(mid) - (1 - mid) * np.log2(1 - mid)
        lo, hi = (mid, hi) if h < target else (lo, mid)
    return lo


def _per_bit(readings, eps):
    """readings[k] = list of observed values for bit k -> (g0, g1) = P(readings | bit = 0/1)."""
    g0 = np.ones(len(readings))
    g1 = np.ones(len(readings))
    for k, rs in enumerate(readings):
        for r in rs:
            g0[k] *= (1 - eps) if r == 0 else eps
            g1[k] *= eps if r == 0 else (1 - eps)
    return g0, g1


def _expand_counts(counts):
    """counts dict -> list of integer clbit values, one per shot."""
    shots = []
    for key, c in counts.items():
        shots += [int(key.replace(" ", ""), 2)] * c
    return shots


def _oracle(n, m):
    return Gate("oracle", n + m, [])


def _normalise_log(logw):
    w = np.exp(logw - logw.max())
    return w / w.sum()


# ----------------------------------------------------------------------------- circuits
def _diffusion(qc, n):
    qc.h(range(n))
    qc.x(range(n))
    qc.h(n - 1)
    qc.mcx(list(range(n - 1)), n - 1)
    qc.h(n - 1)
    qc.x(range(n))
    qc.h(range(n))


def m1_copies(n):
    """Copies per input bit that fit next to the n inputs and the answer qubit."""
    return 1 + (MAX_QUBITS - n - 1) // n


def grover_circuit(n, j, hadamard_readout, copies=1):
    """H^n, answer qubit in |->, j x (oracle, diffusion), optional H^n, then measure the
    inputs; copy c of input k sits on qubit n+1+(c-1)n+k and clbit c*n+k."""
    qc = QuantumCircuit(n + 1 + (copies - 1) * n, copies * n)
    qc.x(n)
    qc.h(n)
    qc.h(range(n))
    for _ in range(j):
        qc.append(_oracle(n, 1), list(range(n + 1)))
        _diffusion(qc, n)
    if hadamard_readout:
        qc.h(range(n))
    for c in range(1, copies):
        for k in range(n):
            qc.cx(k, n + 1 + (c - 1) * n + k)
    qc.measure(range(n), range(n))
    for c in range(1, copies):
        qc.measure([n + 1 + (c - 1) * n + k for k in range(n)], [c * n + k for k in range(n)])
    return qc


def classical_circuit(n, x, y0, copies=1):
    qc = QuantumCircuit(n + copies, copies)
    for k in range(n):
        if (x >> k) & 1:
            qc.x(k)
    if y0:
        qc.x(n)
    qc.append(_oracle(n, 1), list(range(n + 1)))
    for c in range(1, copies):
        qc.cx(n, n + c)
    qc.measure(range(n, n + copies), range(copies))
    return qc


def simon_circuit(n, m, copy_bits=()):
    """H-U-H on the inputs; copy_bits are duplicated onto spare qubits (clbit n+i)."""
    qc = QuantumCircuit(n + m + len(copy_bits), n + len(copy_bits))
    qc.h(range(n))
    qc.append(_oracle(n, m), list(range(n + m)))
    qc.h(range(n))
    for i, k in enumerate(copy_bits):
        qc.cx(k, n + m + i)
    qc.measure(range(n), range(n))
    for i in range(len(copy_bits)):
        qc.measure(n + m + i, n + i)
    return qc


# ----------------------------------------------------------------------------- 2-level model
def two_level(q, j, pm):
    """Exact misfire-averaged state after j Grover iterations for a function whose fraction
    of marked inputs is q (array).  Returns (P[z = 0] with Hadamard readout,
    total probability on marked inputs with computational readout)."""
    q = np.atleast_1d(np.asarray(q, dtype=float))
    th = np.arcsin(np.sqrt(np.clip(q, 0, 1)))
    s = np.stack([np.sin(th), np.cos(th)], axis=-1)              # basis (marked, unmarked)
    D = 2 * s[:, :, None] * s[:, None, :] - np.eye(2)
    O = np.diag([-1.0, 1.0])
    rho = s[:, :, None] * s[:, None, :]
    for _ in range(j):
        rho = (1 - pm) * (O @ rho @ O) + pm * rho
        rho = D @ rho @ D
    p0 = np.einsum("qi,qij,qj->q", s, rho, s)
    pg = rho[:, 0, 0]
    return np.clip(p0, 0, 1), np.clip(pg, 0, 1)


# ----------------------------------------------------------------------------- m = 1 engine
class M1Model:
    """Hypothesis atoms (per noise level):
        constant c (2) | linear (a, b) ((2^n - 1) * 2) | grover t (2^n) | balanced (1) |
        randfun weight w (2^n + 1, binomial prior)
    Answers merge the randfun weight atoms into one answer."""

    def __init__(self, n, families, g_copies, c_copies):
        self.n = n
        N = self.N = 2 ** n
        self.g_copies = g_copies          # readings per input bit in G circuits
        self.c_copies = c_copies          # readings of the answer bit in classical queries
        self.pop = _popcount(n)
        self.bits = _bits_table(n)
        fams = [f for f in M1_FAMILIES if f in families]
        sizes = {"constant": 2, "linear": (N - 1) * 2, "grover": N, "balanced": 1, "randfun": N + 1}
        self.slices = {}
        start = 0
        for fam in M1_FAMILIES:
            self.slices[fam] = slice(start, start + sizes[fam])
            start += sizes[fam]
        self.B = start
        ans = np.arange(self.B)
        rf = self.slices["randfun"]
        ans[rf] = rf.start
        _, self.answer_of = np.unique(ans, return_inverse=True)
        self.n_answers = int(self.answer_of.max()) + 1

        logprior = np.full(self.B, -np.inf)
        for fam in fams:
            sl = self.slices[fam]
            if fam == "randfun":
                logprior[sl] = np.log(1 / len(fams)) + binom.logpmf(np.arange(N + 1), N, RANDFUN_P)
            else:
                logprior[sl] = np.log(1 / len(fams) / sizes[fam])
        self.logw = np.stack([logprior + np.log(p) for p in NOISE_PRIOR])     # (L, B)

        self.lin_a = np.repeat(np.arange(1, N), 2)
        self.lin_b = np.tile([0, 1], N - 1)
        self.q_rand = np.arange(N + 1) / N
        self.design_kernels = [_readout_kernel(n, _design_eps(eps, g_copies)) for _, eps in NOISE_LEVELS]
        self.search_hits = {}          # x -> j of the Grover-search shot that returned x
        # classical reads per input x: f(x) is fixed, so repeated reads of the same x are
        # independent only GIVEN f(x).  For balanced / randfun atoms f(x) is uncertain, so
        # all reads of one x enter through log[pi L1 + (1 - pi) L0] (see _classical_update).
        self.reads = {}                # x -> {"logL": (L, 2) array, "contrib": (L, B) array}
        self._cache = {}

    # -- exact true-outcome distributions P[atom, z] of G(j, readout) per noise level
    def true_dist(self, j, hadamard):
        key = (j, hadamard)
        if key in self._cache:
            return self._cache[key]
        N, S = self.N, self.slices
        out = []
        for pm, _ in NOISE_LEVELS:
            P = np.zeros((self.B, N))
            if hadamard:
                P[S["constant"], 0] = 1.0
                p_odd = (1 - (1 - 2 * (1 - pm)) ** j) / 2           # linear: |0> <-> |a> toggles
                rows = np.arange(S["linear"].start, S["linear"].stop)
                P[rows, 0] = 1 - p_odd
                P[rows, self.lin_a] += p_odd
                qs = np.concatenate([[1.0 / N, 0.5], self.q_rand])
                p0, _ = two_level(qs, j, pm)
                for sl, p in ((S["grover"], p0[:1]), (S["balanced"], p0[1:2]), (S["randfun"], p0[2:])):
                    blk = np.repeat(((1 - p) / (N - 1))[:, None], N, axis=1)
                    blk[:, 0] = p
                    P[sl] = blk
            else:
                P[:] = 1.0 / N
                _, pg = two_level([1.0 / N], j, pm)
                g = np.full((N, N), (1 - pg[0]) / (N - 1))
                np.fill_diagonal(g, pg[0])
                P[S["grover"]] = g
            out.append(P)
        self._cache[key] = out
        return out

    def p_one(self, x):
        """P(f(x) = 1) per atom.  For balanced / randfun an x returned by a Grover search is
        more likely to be marked: use the amplified marked probability of that search."""
        S = self.slices
        pf = np.zeros(self.B)
        pf[S["constant"]] = [0.0, 1.0]
        pf[S["linear"]] = (self.pop[self.lin_a & x] & 1) ^ self.lin_b
        pf[S["grover"].start + x] = 1.0
        if x in self.search_hits:
            j = self.search_hits[x]
            _, pg = two_level(np.concatenate([[0.5], self.q_rand]), j, NOISE_LEVELS[0][0])
            pf[S["balanced"]] = max(0.5, pg[0])
            pf[S["randfun"]] = np.maximum(self.q_rand, pg[1:])
        else:
            pf[S["balanced"]] = 0.5
            pf[S["randfun"]] = self.q_rand
        return pf

    # -- design: approximate outcome tables (L, B, O) with a binary-symmetric readout
    def design_table(self, exp):
        if exp[0] == "G":
            P = self.true_dist(exp[1], exp[2])
            return np.stack([(1 - FLOOR) * Pl @ K.T + FLOOR / self.N
                             for Pl, K in zip(P, self.design_kernels)])
        out = []
        for li, (pm, eps) in enumerate(NOISE_LEVELS):
            pf = self.p_one_given_reads(exp[1], li)
            e = _design_eps(eps, self.c_copies)
            p1 = pm * exp[2] + (1 - pm) * (pf if exp[2] == 0 else 1 - pf)
            p1 = p1 * (1 - e) + (1 - p1) * e
            out.append((1 - FLOOR) * np.stack([1 - p1, p1], axis=-1) + FLOOR / 2)
        return np.stack(out)

    def expected_info_gain(self, table):
        w = _normalise_log(self.logw.ravel()).reshape(self.logw.shape)
        joint_atoms = np.einsum("lb,lbo->bo", w, table)
        J = np.zeros((self.n_answers, table.shape[2]))
        np.add.at(J, self.answer_of, joint_atoms)
        pa = J.sum(1)
        po = J.sum(0)
        h_prior = -np.sum(pa[pa > 0] * np.log(pa[pa > 0]))
        with np.errstate(divide="ignore", invalid="ignore"):
            cond = J / po[None, :]
            h_post = -np.sum(np.where(J > 0, J * np.log(np.where(cond > 0, cond, 1.0)), 0.0))
        return h_prior - h_post

    # -- exact Bayesian update from one shot (raw clbit value v)
    def update(self, exp, v):
        n = self.n
        loglik = []
        for li, (pm, eps) in enumerate(NOISE_LEVELS):
            if exp[0] == "G":
                readings = [[(v >> (c * n + k)) & 1 for c in range(self.g_copies)] for k in range(n)]
                g0, g1 = _per_bit(readings, eps)
                gvec = np.prod(np.where(self.bits == 1, g1[None, :], g0[None, :]), axis=1)
                P = self.true_dist(exp[1], exp[2])[li]
                like = (1 - FLOOR) * (P @ gvec) + FLOOR * gvec.mean()
            else:
                return self._classical_update(exp, v)
            loglik.append(np.log(like))
        self.logw += np.stack(loglik)
        if exp[0] == "G" and not exp[2]:
            x = int(np.argmax(gvec))                 # most likely measured input
            self.search_hits[x] = max(self.search_hits.get(x, 0), exp[1])

    def p_one_given_reads(self, x, li):
        """P(f(x) = 1) per atom after the reads of x seen so far (noise level li)."""
        pi = self.p_one(x)
        if x not in self.reads:
            return pi
        l0, l1 = self.reads[x]["logL"][li]
        r = np.exp(np.clip(l1 - l0, -700, 700))          # likelihood ratio L1 / L0
        return pi * r / (pi * r + (1 - pi))

    def _classical_update(self, exp, v):
        """Classical read of f(x).  Given f(x) = u, one read has likelihood
            l_u = (1 - FLOOR) [pm g(y0) + (1 - pm) g(y0 xor u)] + FLOOR (g0 + g1) / 2
        and reads are independent; all reads of x together contribute
            log[ pi L1 + (1 - pi) L0 ],  L_u = prod over reads of l_u,  pi = P(f(x) = 1 | atom).
        For constant / linear / grover pi is 0 or 1, so this is the usual product; for
        balanced / randfun it stops repeated reads of one x from counting as fresh samples."""
        x, y0 = exp[1], exp[2]
        rs = [(v >> c) & 1 for c in range(self.c_copies)]
        rec = self.reads.setdefault(x, {"logL": np.zeros((len(NOISE_LEVELS), 2)),
                                        "contrib": np.zeros_like(self.logw)})
        pi = self.p_one(x)
        new = np.empty_like(self.logw)
        for li, (pm, eps) in enumerate(NOISE_LEVELS):
            g0, g1 = _per_bit([rs], eps)
            g = (g0[0], g1[0])
            for u in (0, 1):
                l_u = (1 - FLOOR) * (pm * g[y0] + (1 - pm) * g[y0 ^ u]) + FLOOR * 0.5 * (g[0] + g[1])
                rec["logL"][li, u] += np.log(l_u)
            l0, l1 = rec["logL"][li]
            with np.errstate(divide="ignore"):
                new[li] = np.logaddexp(np.log(pi) + l1, np.log1p(-pi) + l0)
        self.logw += new - rec["contrib"]
        rec["contrib"] = new

    def answer_posterior(self):
        w = _normalise_log(self.logw.ravel()).reshape(self.logw.shape).sum(0)
        return np.bincount(self.answer_of, weights=w, minlength=self.n_answers)

    def decode(self, answer):
        atom = int(np.flatnonzero(self.answer_of == answer)[0])
        for fam, sl in self.slices.items():
            if sl.start <= atom < sl.stop:
                i = atom - sl.start
                if fam == "constant":
                    return fam, i
                if fam == "linear":
                    return fam, [int(self.lin_a[i]), int(self.lin_b[i])]
                if fam == "grover":
                    return fam, i
                return fam, None

    def top_grover(self):
        w = _normalise_log(self.logw.ravel()).reshape(self.logw.shape).sum(0)
        return int(np.argmax(w[self.slices["grover"]]))


def solve_m1(n, budget, families, run, menu=("echo", "search", "classical"), rng=None,
             delta=DELTA, readout_copies=True, log=None, schedule=None):
    """Adaptive m = 1 solver.  `menu` restricts the circuit types (used for baselines);
    `schedule` replaces adaptivity with a fixed list of experiments (non-adaptive baseline)."""
    rng = rng or np.random.default_rng()
    g_copies = m1_copies(n) if readout_copies else 1
    c_copies = 3 if readout_copies else 1
    model = M1Model(n, families, g_copies, c_copies)
    used = 0
    used_x = set()
    y0_next = 0
    queue = list(schedule) if schedule is not None else None
    while True:
        post = model.answer_posterior()
        if queue is None and post.max() >= 1 - delta:
            break
        remaining = budget - used
        if queue is not None:
            if not queue:
                break
            exp = queue.pop(0)
            if exp[0] == "C" and exp[1] is None:
                fresh = [x for x in range(2 ** n) if x not in used_x]
                exp = ("C", int(rng.choice(fresh)), y0_next)
            elif exp[0] == "C":
                exp = ("C", exp[1], y0_next)
            cost = exp[1] if exp[0] == "G" else 1
            if cost > remaining:
                continue
            score = None
        else:
            options = []
            if "echo" in menu:
                options += [("G", j, True) for j in ECHO_JS if j <= remaining]
            elif "dj" in menu and remaining >= 1:
                options += [("G", 1, True)]
            if "search" in menu:
                options += [("G", j, False) for j in SEARCH_JS if j <= remaining]
            if "classical" in menu and remaining >= 1:
                fresh = [x for x in range(2 ** n) if x not in used_x]
                xr = int(rng.choice(fresh)) if fresh else int(rng.integers(2 ** n))
                options += [("C", xr, y0_next), ("C", model.top_grover(), y0_next)]
            if not options:
                break
            exp, score = None, -1.0
            for opt in options:
                s = model.expected_info_gain(model.design_table(opt)) / (opt[1] if opt[0] == "G" else 1)
                if s > score:
                    exp, score = opt, s
        if exp[0] == "G":
            qc = grover_circuit(n, exp[1], exp[2], g_copies)
            used += exp[1]
        else:
            qc = classical_circuit(n, exp[1], exp[2], c_copies)
            used_x.add(exp[1])
            y0_next ^= 1
            used += 1
        for v in _expand_counts(run(qc, 1)):
            model.update(exp, v)
        if log is not None:
            log.append({"exp": [str(e) for e in exp], "score": None if score is None else round(float(score), 4),
                        "queries": used, "top": round(float(model.answer_posterior().max()), 5)})
    post = model.answer_posterior()
    return model.decode(int(np.argmax(post)))


# ----------------------------------------------------------------------------- m = 8 engine
def _subspaces_2d(N):
    trip = []
    for a in range(1, N):
        for b in range(a + 1, N):
            c = a ^ b
            if c > b:
                trip.append((a, b, c))
    return np.array(trip, dtype=np.int64)


class M8Model:
    """Hypotheses: perm | simon s (N - 1) | simon2 H (every 2-dim subspace), x noise levels.

    With per-bit readout likelihoods g_k(0), g_k(1) for one shot, the probability of the
    readings under hidden subspace V is
        prod_k (g_k(0)+g_k(1)) * [ (1-pm)/N * sum_{v in V} prod_{k in v} c_k  +  pm * prod_k g_k(0)/(g_k(0)+g_k(1)) ]
    with c_k = (g_k(0) - g_k(1)) / (g_k(0) + g_k(1)) (Walsh transform over the annihilator)."""

    def __init__(self, n, families):
        self.n = n
        N = self.N = 2 ** n
        self.bits = _bits_table(n)
        self.triples = _subspaces_2d(N)
        fams = [f for f in M8_FAMILIES if f in families]
        sizes = {"perm": 1, "simon": N - 1, "simon2": len(self.triples)}
        self.slices = {}
        start = 0
        for fam in M8_FAMILIES:
            self.slices[fam] = slice(start, start + sizes[fam])
            start += sizes[fam]
        self.H = start
        logprior = np.full(self.H, -np.inf)
        for fam in fams:
            logprior[self.slices[fam]] = np.log(1.0 / len(fams) / sizes[fam])
        self.logw = np.stack([logprior + np.log(p) for p in NOISE_PRIOR])

    def update(self, readings):
        t = self.triples
        rows = []
        for pm, eps in NOISE_LEVELS:
            g0, g1 = _per_bit(readings, eps)
            tot = g0 + g1
            c = (g0 - g1) / tot
            T = np.prod(np.where(self.bits == 1, c[None, :], 1.0), axis=1)      # T[v]
            mis = np.prod(g0 / tot)
            base = np.empty(self.H)
            base[self.slices["perm"]] = 1.0
            base[self.slices["simon"]] = 1.0 + T[1:]
            base[self.slices["simon2"]] = 1.0 + T[t[:, 0]] + T[t[:, 1]] + T[t[:, 2]]
            P = (1 - pm) * base / self.N + pm * mis
            P = (1 - FLOOR) * P + FLOOR / self.N
            rows.append(np.log(P) + np.sum(np.log(tot)))
        self.logw += np.stack(rows)

    def posterior(self):
        return _normalise_log(self.logw.ravel()).reshape(self.logw.shape).sum(0)

    def decode(self, h):
        for fam, sl in self.slices.items():
            if sl.start <= h < sl.stop:
                i = h - sl.start
                if fam == "perm":
                    return fam, None
                if fam == "simon":
                    return fam, i + 1
                return fam, [int(v) for v in self.triples[i]]


def solve_m8(n, m, budget, families, run, first_batch=6, delta=DELTA, readout_copies=True,
             log=None, fixed_shots=None):
    model = M8Model(n, families)
    spare = MAX_QUBITS - n - m if readout_copies else 0
    # rotate which input bits get a duplicate readout so every bit is protected equally often
    groups = [tuple((g * spare + i) % n for i in range(min(spare, n))) for g in range(n)] if spare else [()]
    groups = list(dict.fromkeys(groups))
    used = 0
    shot_index = 0
    target = fixed_shots or first_batch
    while used < budget:
        shots_now = min(target, budget - used)
        for _ in range(shots_now):
            cb = groups[shot_index % len(groups)]
            shot_index += 1
            qc = simon_circuit(n, m, cb)
            v = _expand_counts(run(qc, 1))[0]
            used += 1
            readings = [[(v >> k) & 1] for k in range(n)]
            for i, k in enumerate(cb):
                readings[k].append((v >> (n + i)) & 1)
            model.update(readings)
        post = model.posterior()
        if log is not None:
            log.append({"queries": used, "top": round(float(post.max()), 5)})
        if fixed_shots is not None or post.max() >= 1 - delta:
            break
        target = 1
    return model.decode(int(np.argmax(model.posterior())))


# ----------------------------------------------------------------------------- entry point
def solve(n, m, budget, families, run):
    if m == 1:
        return solve_m1(n, budget, families, run, rng=np.random.default_rng(SEED))
    return solve_m8(n, m, budget, families, run)
