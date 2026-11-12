"""
test_benchmark.py -- checks for the parts test_quantum_engine.py does not cover:
classical_solver, map_engine, sa_numpy, benchmark (build_series / cache_meta / json round trip).

Run:  python test_benchmark.py
"""
import itertools, json

import numpy as np

from qubo_builder import build_qubo, route_cost, decode_route
from classical_solver import solve_classical_route, solve_heuristic_route
from map_engine import (generate_mission, segment_fraction_in_circle,
                        segment_fraction_in_circle_shapely, route_threat_stats)
import benchmark as B
import sa_numpy


def brute(W):
    n = len(W)
    return min(route_cost([0, *p], W) for p in itertools.permutations(range(1, n)))


def test_held_karp_matches_brute_force():
    for n in range(3, 9):
        for seed in range(3):
            W = generate_mission(n, 3, seed=seed).W
            r = solve_classical_route(W)
            assert r.status == "optimal" and r.route[0] == 0 and sorted(r.route) == list(range(n))
            assert abs(r.cost - brute(W)) < 1e-6 and abs(route_cost(r.route, W) - r.cost) < 1e-6
    print("PASS Held-Karp == brute force (N=3..8, 3 seeds each)")


def test_heuristic_is_valid_and_never_beats_optimum():
    for n in (6, 8, 10):
        W = generate_mission(n, 3, seed=n).W
        h, e = solve_heuristic_route(W), solve_classical_route(W)
        assert sorted(h.route) == list(range(n)) and h.cost >= e.cost - 1e-9
    print("PASS heuristic returns valid tours, cost >= optimum")


def test_exact_solver_limits():
    W = generate_mission(20, 3).W
    assert solve_classical_route(W, max_memory_gb=0.001).status == "skipped_memory"
    assert solve_classical_route(W, timeout=1e-6).status == "timeout"
    print("PASS exact solver reports skipped_memory / timeout")


def test_threat_geometry():
    assert abs(segment_fraction_in_circle([0, 0], [10, 0], [5, 0], 2) - 0.4) < 1e-12
    assert segment_fraction_in_circle([0, 0], [10, 0], [5, 9], 2) == 0.0
    a = segment_fraction_in_circle([0, 0], [10, 0], [5, 1], 3)
    b = segment_fraction_in_circle_shapely([0, 0], [10, 0], [5, 1], 3)
    assert abs(a - b) < 0.01
    m = generate_mission(8, 3, seed=1)
    s = route_threat_stats(list(range(8)), m)
    assert s["km_in_threat"] <= s["km_total"] + 1e-9
    print("PASS threat geometry (analytic, shapely agreement, stats)")


def test_numpy_annealer_finds_feasible_optimum_small():
    W = generate_mission(5, 2, seed=3).W
    Q, off, _ = build_qubo(W, penalty=10 * W.max())
    X, E, done = sa_numpy.anneal(Q, 25, num_reads=32, sweeps=300, seed=1, max_seconds=20)
    best = None
    for x in X:
        r, ok = decode_route({k: int(v) for k, v in enumerate(x)}, 5)
        if ok:
            c = route_cost(r, W); best = c if best is None else min(best, c)
    assert best is not None, "numpy annealer found no feasible tour at N=5"
    assert best <= brute(W) * 1.05 + 1e-9, (best, brute(W))
    # energies it reports must equal the QUBO energy of its samples
    M = np.zeros((25, 25))
    for (u, v), c in Q.items(): M[u, v] += c
    assert np.allclose(E, np.einsum("ri,ij,rj->r", X, M, X))
    print(f"PASS numpy annealer: feasible tour within 5% of optimum at N=5 ({done} sweeps)")


def test_benchmark_rows_series_and_cache():
    rows = B.run_benchmark([5, 8, 10, 12, 14, 16], run_annealer=True, anneal_reads=8,
                           anneal_sweeps=100, exact_timeout=10, max_memory_gb=0.001 * 0 + 0.002)
    # tiny memory cap forces the larger sizes to be "skipped_memory" -> exercises the wall + extrapolation
    s = B.build_series(rows, B.QPUModel(), extrapolate=True)
    for k in ("exact_measured", "exact_extrap", "heuristic", "annealer_sim", "qpu_projected",
              "hybrid_min", "pure_qpu_max_n", "exact_wall_n"):
        assert k in s
    assert s["pure_qpu_max_n"] == 12
    assert all(n <= 12 for n in s["qpu_projected"][0])
    assert s["exact_wall_n"] is not None
    for r in rows:                                   # reference cost must never be above any method's cost
        assert r.ref_cost <= r.heur_cost + 1e-9
        if r.ann_cost: assert r.ref_cost <= r.ann_cost + 1e-9
    back = B.rows_from_dicts(json.loads(json.dumps(B.rows_to_dicts(rows))))
    assert [r.n for r in back] == [r.n for r in rows]
    meta = B.cache_meta()
    assert {"saved", "platform", "annealer_impl"} <= set(meta)
    print("PASS benchmark rows / build_series / cache_meta / JSON round trip")


def test_human_time():
    assert B.human_time(None) == "-" and B.human_time(0.0152) == "15.2 ms"
    print("PASS human_time")


if __name__ == "__main__":
    test_held_karp_matches_brute_force()
    test_heuristic_is_valid_and_never_beats_optimum()
    test_exact_solver_limits()
    test_threat_geometry()
    test_numpy_annealer_finds_feasible_optimum_small()
    test_benchmark_rows_series_and_cache()
    test_human_time()
    print("\nAll benchmark tests passed.")
