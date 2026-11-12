"""
classical_solver.py -- classical baselines  (roadmap Hour 9-12)

solve_classical_route    exact Held-Karp DP, O(N^2 * 2^N), with a time limit.
solve_heuristic_route    nearest-neighbour + 2-opt (fast, NOT guaranteed optimal).
                         Not in the roadmap's solver list; added because classical
                         heuristics are the fair comparison at large N (roadmap §1.1
                         itself names heuristics as the classical alternative).

Timeout: the roadmap suggests a threading.Timer that "kills" the solver thread.
Python cannot safely kill a thread, so the DP checks a deadline between layers
and stops itself (same visible result: "TIMEOUT").
"""
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from qubo_builder import route_cost


@dataclass
class ClassicalResult:
    route: Optional[list]     # None unless a route was found
    cost: Optional[float]
    exec_time: float          # seconds actually spent
    status: str               # "optimal" | "timeout" | "skipped_memory" | "heuristic"
    note: str = ""


def held_karp_memory_gb(n):
    """Approximate DP table size (float64, 2^(N-1) x (N-1))."""
    m = n - 1
    return (2 ** m) * m * 8 / 1e9


def solve_classical_route(W, timeout=15.0, max_memory_gb=1.0):
    """Exact optimal closed tour from node 0 (Held-Karp). Vectorised with numpy."""
    W = np.asarray(W, dtype=float)
    n = W.shape[0]
    t0 = time.perf_counter()

    if n < 2:
        raise ValueError("need at least 2 nodes")
    if n == 2:
        return ClassicalResult([0, 1], route_cost([0, 1], W),
                               time.perf_counter() - t0, "optimal")

    mem = held_karp_memory_gb(n)
    if mem > max_memory_gb:
        return ClassicalResult(
            None, None, time.perf_counter() - t0, "skipped_memory",
            f"DP table would need ~{mem:.1f} GB (limit {max_memory_gb} GB)")

    m = n - 1                                   # nodes 1..N-1 -> bits 0..m-1
    Wm = W[1:, 1:]                              # Wm[a, b] = W[a+1, b+1]
    full = (1 << m) - 1
    dp = np.full((1 << m, m), np.inf)
    for j in range(m):
        dp[1 << j, j] = W[0, j + 1]

    masks = np.arange(1 << m)
    popcount = np.zeros(1 << m, dtype=np.int8)
    for b in range(m):
        popcount += ((masks >> b) & 1).astype(np.int8)

    for size in range(2, m + 1):
        layer = masks[popcount == size]
        for k in range(m):
            if time.perf_counter() - t0 > timeout:
                return ClassicalResult(None, None, time.perf_counter() - t0,
                                       "timeout", f"exceeded {timeout:g}s")
            sel = layer[(layer >> k) & 1 == 1]
            prev = sel ^ (1 << k)
            dp[sel, k] = (dp[prev, :] + Wm[:, k][None, :]).min(axis=1)

    closing = dp[full, :] + W[1:, 0]
    j = int(np.argmin(closing))
    best = float(closing[j])

    route_rev, mask = [], full                  # backtrack from the last node
    while True:
        route_rev.append(j + 1)
        prev_mask = mask ^ (1 << j)
        if prev_mask == 0:
            break
        j_prev = int(np.argmin(dp[prev_mask, :] + Wm[:, j]))
        mask, j = prev_mask, j_prev
    route = [0] + route_rev[::-1]
    return ClassicalResult(route, best, time.perf_counter() - t0, "optimal")


def solve_heuristic_route(W, max_passes=100):
    """Nearest-neighbour construction followed by 2-opt improvement."""
    W = np.asarray(W, dtype=float)
    n = W.shape[0]
    t0 = time.perf_counter()

    route, left = [0], set(range(1, n))
    while left:
        nxt = min(left, key=lambda j: W[route[-1], j])
        route.append(nxt)
        left.remove(nxt)

    cost = route_cost(route, W)
    for _ in range(max_passes):
        improved = False
        for a in range(1, n - 1):
            for b in range(a + 1, n):
                cand = route[:a] + route[a:b + 1][::-1] + route[b + 1:]
                c = route_cost(cand, W)
                if c < cost - 1e-9:
                    route, cost, improved = cand, c, True
        if not improved:
            break
    return ClassicalResult(route, cost, time.perf_counter() - t0, "heuristic",
                           "nearest-neighbour + 2-opt (no optimality guarantee)")
