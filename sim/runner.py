"""Local stand-in for the judges' run(circuit, shots), following section 3 of the statement.

* The placeholder Gate("oracle", n+m) acts as U|x>|y> = |x>|y XOR f(x)>, with qubit k = bit k.
* Each oracle application misfires independently per shot with probability p_misfire
  (it then acts as the identity).
* Each measured classical bit flips independently with probability p_flip.
* Counts are keyed by classical-bit strings in Qiskit order (clbit 0 rightmost).
* One query = one oracle gate in one shot; exceeding the budget raises BudgetExceeded.

The simulator is a plain numpy state vector (<= 20 qubits) that only allocates qubits once a
gate touches them. Shots are grouped by their misfire pattern so each distinct pattern is
simulated once.
"""
import numpy as np
from qiskit.circuit import ControlledGate
from qiskit.quantum_info import Operator


class BudgetExceeded(RuntimeError):
    pass


_SQRT1_2 = 1 / np.sqrt(2)


class _LazyState:
    """State tensor over the qubits touched so far; untouched qubits are |0> and are added
    as a new (last) axis the first time a gate acts on them.  axis i <-> self.active[i]."""

    def __init__(self):
        self.st = np.ones((), dtype=complex)
        self.active = []

    def axis(self, q):
        if q not in self.active:
            self.st = np.stack([self.st, np.zeros_like(self.st)], axis=-1)
            self.active.append(q)
        return self.active.index(q)

    def apply_1q(self, U, q, name):
        a = self.axis(q)
        lead = (slice(None),) * a
        s0, s1 = self.st[lead + (0,)], self.st[lead + (1,)]
        if name == "h":
            new = [(s0 + s1) * _SQRT1_2, (s0 - s1) * _SQRT1_2]
        elif name == "x":
            new = [s1, s0]
        else:
            new = [U[0, 0] * s0 + U[0, 1] * s1, U[1, 0] * s0 + U[1, 1] * s1]
        self.st = np.stack(new, axis=a)

    def apply_kq(self, U, qs):
        k = len(qs)
        axes = [self.axis(q) for q in reversed(qs)]  # qubits qs[k-1]..qs[0]
        Ut = U.reshape([2] * (2 * k))                 # (out_{k-1}..out_0, in_{k-1}..in_0)
        out = np.tensordot(Ut, self.st, axes=(list(range(k, 2 * k)), axes))
        self.st = np.moveaxis(out, list(range(k)), axes)

    def apply_mcx(self, controls, target):
        c_axes = [self.axis(c) for c in controls]
        t = self.axis(target)
        idx = [slice(None)] * self.st.ndim
        for a in c_axes:
            idx[a] = 1
        idx = tuple(idx)
        t_sub = t - sum(1 for a in c_axes if a < t)
        st = self.st.copy()
        st[idx] = np.flip(st[idx], axis=t_sub).copy()
        self.st = st

    def apply_oracle(self, f, xq, yq, cache):
        for q in list(xq) + list(yq):
            self.axis(q)
        key = (tuple(self.active), tuple(xq), tuple(yq))
        if key in cache:
            new = cache[key]
        else:
            L = len(self.active)
            pos = {q: L - 1 - i for i, q in enumerate(self.active)}   # flat-index bit of qubit q
            idx = np.arange(2 ** L, dtype=np.int64)
            x = np.zeros_like(idx)
            for k, q in enumerate(xq):
                x |= ((idx >> pos[q]) & 1) << k
            y = np.zeros_like(idx)
            for k, q in enumerate(yq):
                y |= ((idx >> pos[q]) & 1) << k
            y2 = y ^ f[x]
            new = idx.copy()
            for k, q in enumerate(yq):
                new &= ~(1 << pos[q])
                new |= ((y2 >> k) & 1) << pos[q]
            cache[key] = new
        flat = np.ascontiguousarray(self.st).reshape(-1)
        nxt = np.empty_like(flat)
        nxt[new] = flat
        self.st = nxt.reshape(self.st.shape)


def measured_distribution(circuit, f, n, fired, cache=None):
    """Exact distribution over the integer value of the classical register for one
    misfire pattern (`fired[i]` says whether the i-th oracle call acts)."""
    if circuit.num_qubits > 20:
        raise ValueError("more than 20 qubits")
    cache = {} if cache is None else cache
    S = _LazyState()
    measures = []
    k_oracle = 0
    for inst in circuit.data:
        op = inst.operation
        qs = [circuit.find_bit(q).index for q in inst.qubits]
        name = op.name
        if name == "oracle":
            if fired[k_oracle]:
                S.apply_oracle(f, qs[:n], qs[n:], cache)
            k_oracle += 1
        elif name == "measure":
            measures.append((qs[0], circuit.find_bit(inst.clbits[0]).index))
        elif name in ("barrier", "id", "delay"):
            continue
        elif (isinstance(op, ControlledGate) and op.base_gate.name == "x"
              and op.ctrl_state == 2 ** op.num_ctrl_qubits - 1):
            S.apply_mcx(qs[:-1], qs[-1])
        elif len(qs) == 1:
            S.apply_1q(None if name in ("h", "x") else Operator(op).data, qs[0], name)
        else:
            S.apply_kq(Operator(op).data, qs)
    # marginal over the measured (active) qubits; never-touched qubits read 0
    probs = np.abs(S.st) ** 2
    mq = [q for q in S.active if q in {q for q, _ in measures}]
    keep = [S.active.index(q) for q in mq]
    marg = probs.sum(axis=tuple(a for a in range(len(S.active)) if a not in keep))
    marg = marg.reshape(-1)
    clbit_of = dict(measures)
    sub = np.arange(2 ** len(mq))
    val = np.zeros_like(sub)
    for i, q in enumerate(mq):                        # axis order: mq[0] most significant
        val |= ((sub >> (len(mq) - 1 - i)) & 1) << clbit_of[q]
    dist = np.bincount(val, weights=marg, minlength=2 ** circuit.num_clbits)
    return dist / dist.sum(), [c for _, c in measures]


class OracleRunner:
    """Callable run(circuit, shots) bound to one sealed oracle."""

    def __init__(self, oracle, budget=60, p_misfire=0.04, p_flip=0.02, seed=None):
        self.oracle = oracle
        self.f = np.asarray(oracle.f, dtype=np.int64)
        self.n = oracle.n
        self.budget = budget
        self.p_misfire = p_misfire
        self.p_flip = p_flip
        self.rng = np.random.default_rng(seed)
        self.queries = 0
        self.calls = []
        self._perm_cache = {}

    def __call__(self, circuit, shots):
        shots = int(shots)
        k = sum(1 for inst in circuit.data if inst.operation.name == "oracle")
        cost = k * shots
        if self.queries + cost > self.budget:
            raise BudgetExceeded(f"{self.queries}+{cost} > {self.budget}")
        self.queries += cost
        ncl = circuit.num_clbits
        fired = self.rng.random((shots, k)) >= self.p_misfire
        patterns, multiplicity = np.unique(fired, axis=0, return_counts=True)
        outcomes = []
        for pat, mult in zip(patterns, multiplicity):
            dist, measured = measured_distribution(circuit, self.f, self.n, pat, self._perm_cache)
            draws = self.rng.choice(2 ** ncl, size=mult, p=dist)
            flip_mask = np.zeros(mult, dtype=np.int64)
            flips = self.rng.random((mult, len(measured))) < self.p_flip
            for j, c in enumerate(measured):
                flip_mask |= flips[:, j].astype(np.int64) << c
            outcomes.append(draws ^ flip_mask)
        outcomes = np.concatenate(outcomes)
        counts = {}
        for v in outcomes:
            key = format(int(v), f"0{ncl}b")
            counts[key] = counts.get(key, 0) + 1
        self.calls.append({"oracle_gates": k, "shots": shots, "counts": counts})
        return counts
