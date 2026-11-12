"""
test_quantum_engine.py -- offline checks for qubo_builder.py and quantum_solver.py

Part 1 (QUBO math) uses only numpy: brute-forces every binary state.
Part 2 (solver control flow) injects STAND-IN dimod / neal / dwave.system modules
so it runs without the Ocean SDK or a Leap token. It checks *our* logic
(backend choice, fallback, timing, infeasible handling) -- it does NOT test D-Wave.

Run:  python test_quantum_engine.py
"""
import itertools
import sys
import types

import numpy as np

from qubo_builder import build_qubo, decode_route, route_cost, var_index


# ----------------------------------------------------------------- helpers
def random_W(N, seed):
    rng = np.random.default_rng(seed)
    pts = rng.uniform(0, 100, (N, 2))
    d = np.linalg.norm(pts[:, None] - pts[None], axis=2)
    threat = 1 + 20 * (rng.random((N, N)) < 0.3)          # some edges heavily penalised
    W = d * threat
    np.fill_diagonal(W, 0)
    return (W + W.T) / 2


def qubo_energies_all_states(Q, offset, n):
    """Energy of all 2^n binary states (vectorised)."""
    M = np.zeros((n, n))
    for (u, v), c in Q.items():
        M[u, v] += c
    X = ((np.arange(2 ** n)[:, None] >> np.arange(n)) & 1).astype(float)
    return X, np.einsum("si,ij,sj->s", X, M, X) + offset


def sample_from_bits(bits):
    return {k: int(b) for k, b in enumerate(bits)}


def brute_force_tsp(W):
    N = len(W)
    best = min(itertools.permutations(range(1, N)),
               key=lambda p: route_cost([0, *p], W))
    return [0, *best], route_cost([0, *best], W)


# ------------------------------------------------------ Part 1: QUBO math
def test_ground_state_is_optimal_tour():
    for seed in range(5):
        N = 4
        W = random_W(N, seed)
        Q, offset, lam = build_qubo(W)
        X, E = qubo_energies_all_states(Q, offset, N * N)
        best = int(np.argmin(E))
        route, ok = decode_route(sample_from_bits(X[best]), N)
        opt_route, opt_cost = brute_force_tsp(W)
        assert ok, f"seed {seed}: ground state infeasible"
        assert abs(E[best] - opt_cost) < 1e-6, (E[best], opt_cost)
        assert abs(route_cost(route, W) - opt_cost) < 1e-6
    print("PASS ground state == optimal tour (N=4, 5 instances, exhaustive)")


def test_every_valid_tour_energy_equals_cost():
    for N in (4, 5, 6):
        W = random_W(N, 100 + N)
        Q, offset, _ = build_qubo(W)
        n = N * N
        M = np.zeros((n, n))
        for (u, v), c in Q.items():
            M[u, v] += c
        for perm in itertools.permutations(range(1, N)):
            route = [0, *perm]
            x = np.zeros(n)
            for p, i in enumerate(route):
                x[var_index(i, p, N)] = 1
            e = x @ M @ x + offset
            assert abs(e - route_cost(route, W)) < 1e-6
    print("PASS valid-tour energy == weighted tour length (N=4,5,6)")


def test_all_infeasible_states_cost_more_than_optimum():
    N = 4
    W = random_W(N, 7)
    Q, offset, _ = build_qubo(W)
    X, E = qubo_energies_all_states(Q, offset, N * N)
    _, opt = brute_force_tsp(W)
    for x, e in zip(X, E):
        _, ok = decode_route(sample_from_bits(x), N)
        if not ok:
            assert e > opt + 1e-9, "an infeasible state beats the optimum"
    print("PASS no infeasible state undercuts the optimum (N=4, exhaustive)")


def test_decode_rejects_bad_samples():
    N = 3
    good = {var_index(i, p, N): int(i == p) for i in range(N) for p in range(N)}
    assert decode_route(good, N) == ([0, 1, 2], True)
    two_in_step = dict(good); two_in_step[var_index(2, 0, N)] = 1
    assert decode_route(two_in_step, N) == (None, False)
    dup = {var_index(0, 0, N): 1, var_index(1, 1, N): 1, var_index(1, 2, N): 1}
    assert decode_route(dup, N) == (None, False)
    not_depot = {var_index(1, 0, N): 1, var_index(0, 1, N): 1, var_index(2, 2, N): 1}
    assert decode_route(not_depot, N) == (None, False)
    print("PASS decode_route rejects multi-node steps, duplicates, non-depot start")


# ------------------------------- Part 2: solver control flow (stand-in SDK)
class FakeBQM:
    def __init__(self, Q, offset): self.Q, self.offset = Q, offset
    @classmethod
    def from_qubo(cls, Q, offset=0.0): return cls(Q, offset)


class Datum:
    def __init__(self, sample, energy): self.sample, self.energy = sample, energy


class FakeSampleSet:
    def __init__(self, rows, info=None):
        self.rows = sorted(rows, key=lambda r: r[1]); self.info = info or {}
    @property
    def first(self): return Datum(*self.rows[0])
    def data(self, fields, sorted_by="energy"):
        return [Datum(s, e) for s, e in self.rows]


class FakeSA:
    """Exhaustive 'annealer' for <=16 variables: returns the 20 lowest states."""
    def sample(self, bqm, num_reads=1, **kw):
        n = len({u for k in bqm.Q for u in k})
        X, E = qubo_energies_all_states(bqm.Q, bqm.offset, n)
        idx = np.argsort(E)[:20]
        return FakeSampleSet([(sample_from_bits(X[i]), float(E[i])) for i in idx])


STATE = {"qpu_fails": False, "hybrid_fails": False, "infeasible_first": False}


class FakeDWaveSampler:
    def __init__(self):
        if STATE["qpu_fails"]:
            raise ConnectionError("no route to host (simulated)")


class FakeEmbeddingComposite:
    def __init__(self, child): pass
    def sample(self, bqm, num_reads=1, label=None, **kw):
        ss = FakeSA().sample(bqm)
        ss.info = {"timing": {"qpu_access_time": 15200.0}}      # microseconds
        if STATE["infeasible_first"]:                           # lowest-energy row is garbage
            ss.rows.insert(0, ({k: 0 for k in ss.rows[0][0]}, -1e9))
        return ss


class FakeHybrid:
    def __init__(self):
        if STATE["hybrid_fails"]: raise RuntimeError("hybrid unavailable (simulated)")
    def sample(self, bqm, label=None, time_limit=None, **kw):
        ss = FakeSA().sample(bqm)
        ss.info = {"qpu_access_time": 30000.0, "run_time": 3_000_000.0}
        return ss


def install_fakes():
    dimod = types.ModuleType("dimod"); dimod.BinaryQuadraticModel = FakeBQM
    neal = types.ModuleType("neal"); neal.SimulatedAnnealingSampler = FakeSA
    dwave = types.ModuleType("dwave"); system = types.ModuleType("dwave.system")
    system.DWaveSampler = FakeDWaveSampler
    system.EmbeddingComposite = FakeEmbeddingComposite
    system.LeapHybridSampler = FakeHybrid
    dwave.system = system
    sys.modules.update({"dimod": dimod, "neal": neal, "dwave": dwave, "dwave.system": system})


def test_solver_flow():
    install_fakes()
    from quantum_solver import solve_quantum_route, solve_quantum_route_full

    N = 4
    W = random_W(N, 3)
    Q, offset, _ = build_qubo(W)
    _, opt = brute_force_tsp(W)

    # 1. QPU path: real-QPU timing read from info, converted us -> s
    r = solve_quantum_route_full(Q, offset, backend="qpu")
    assert r.valid and not r.fallback_used and r.backend == "qpu" and r.timing_is_qpu
    assert abs(r.qpu_time - 0.0152) < 1e-9
    assert abs(route_cost(r.route, W) - opt) < 1e-6 and abs(r.energy - opt) < 1e-6

    # 2. Roadmap-signature wrapper
    route, energy, t = solve_quantum_route(Q, offset)
    assert route[0] == 0 and abs(t - 0.0152) < 1e-9

    # 3. Hybrid path reads top-level qpu_access_time
    r = solve_quantum_route_full(Q, offset, backend="hybrid")
    assert r.backend == "hybrid" and abs(r.qpu_time - 0.03) < 1e-9

    # 4. Network/QPU failure -> simulated-annealing fallback, clearly flagged
    STATE["qpu_fails"] = True
    r = solve_quantum_route_full(Q, offset, backend="qpu")
    assert r.fallback_used and r.backend == "simulator" and not r.timing_is_qpu
    assert "ConnectionError" in r.fallback_reason and r.valid
    STATE["qpu_fails"] = False

    # 5. Explicit simulator choice (UI checkbox off): no fallback flag
    r = solve_quantum_route_full(Q, offset, backend="simulator")
    assert r.backend == "simulator" and not r.fallback_used and not r.timing_is_qpu

    # 6. Infeasible lowest-energy sample is skipped, feasible one returned
    STATE["infeasible_first"] = True
    r = solve_quantum_route_full(Q, offset, backend="qpu")
    assert r.valid and r.route[0] == 0 and abs(r.energy - opt) < 1e-6
    STATE["infeasible_first"] = False

    # 7. Bad inputs fail loudly
    for bad in ({(0, 0): 1.0, (1, 1): 1.0}, ):                 # 2 variables, not N^2
        try:
            solve_quantum_route_full(bad); raise SystemExit("expected ValueError")
        except ValueError:
            pass
    try:
        solve_quantum_route_full(Q, offset, backend="bogus"); raise SystemExit("expected ValueError")
    except ValueError:
        pass
    print("PASS solver flow: qpu / hybrid / fallback / simulator / infeasible-skip / bad input")


if __name__ == "__main__":
    test_ground_state_is_optimal_tour()
    test_every_valid_tour_energy_equals_cost()
    test_all_infeasible_states_cost_more_than_optimum()
    test_decode_rejects_bad_samples()
    test_solver_flow()
    print("\nAll tests passed.")
