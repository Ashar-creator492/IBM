"""
race_engine.py -- data layer for the Q-Route "race" dashboard.

Pure Python + numpy (no Streamlit / plotly), so it is testable offline and the UI
file stays thin.  EVERY number it produces is labelled with where it came from:

    measured    wall-clock time of code that actually ran on this machine
    simulated   a classical simulation of an annealer (simulated annealing on the
                same N^2-variable QUBO).  Its time is CPU time, NOT QPU time.
    extrapolated  a curve fitted to measured Held-Karp points, drawn past the
                point where the exact solver could no longer be run
    projected   a model of D-Wave QPU access time built from D-Wave's published
                timing structure.  Nothing here was run on a QPU.

No time.sleep() "fake" timings anywhere.

Series produced per problem size N (nodes incl. depot -> N^2 QUBO bits):
    exact       Held-Karp (classical_solver.solve_classical_route)     measured
    heuristic   nearest-neighbour + 2-opt                              measured
    annealer    simulated annealing on the QUBO                        simulated
    qpu_proj    projected D-Wave QPU access time (pure QPU)            projected
    hybrid_proj documented minimum Leap-hybrid run time                documented
"""
from __future__ import annotations

import time
from dataclasses import dataclass, asdict, field
from typing import Optional

import numpy as np

from classical_solver import solve_classical_route, solve_heuristic_route
from map_engine import generate_mission, route_threat_stats
from qubo_builder import build_qubo, decode_route, route_cost

# --------------------------------------------------------------------------
# Projection assumptions (all editable in the dashboard sidebar).
# Source: D-Wave docs "Operation and Timing" (programming time typically
# 10-20 ms; per-read = anneal + readout + delay, ~0.08-0.25 ms on Advantage).
# --------------------------------------------------------------------------
@dataclass
class QPUModel:
    programming_ms: float = 16.0      # typical 10-20 ms
    anneal_us: float = 20.0           # default anneal time per read
    readout_us: float = 60.0          # ~25 us (small) .. ~150 us (large) per read
    delay_us: float = 21.0            # inter-read delay (example value in docs)
    num_reads: int = 100              # same as roadmap snippet
    # Largest complete graph on an IDEAL Pegasus (100 % yield) is K150 per D-Wave
    # docs; real chips are smaller.  N^2 logical bits must form a dense-enough
    # problem to embed, so the pure-QPU limit is about floor(sqrt(clique)).
    max_clique: int = 150

    def access_seconds(self) -> float:
        per_read_us = self.anneal_us + self.readout_us + self.delay_us
        return (self.programming_ms * 1e3 + self.num_reads * per_read_us) / 1e6

    def max_nodes_pure_qpu(self) -> int:
        return int(np.floor(np.sqrt(self.max_clique)))


def hybrid_min_time_limit_s(n_vars: int) -> float:
    """
    Minimum run time D-Wave documents for the Leap hybrid BQM solver
    (piecewise-linear; sample points from the BQM solver properties page:
    3 s up to 1,024 vars, 10 s at 4,096, 40 s at 10,000, ...).
    Only the range this project needs is encoded; treat as approximate and
    re-read `LeapHybridSampler.min_time_limit(bqm)` on the real SDK.
    """
    pts_x = [0, 1024, 4096, 10000, 30000, 100000]
    pts_y = [3.0, 3.0, 10.0, 40.0, 200.0, 600.0]
    return float(np.interp(n_vars, pts_x, pts_y))


# --------------------------------------------------------------------------
# Annealer (simulated) -- uses neal / dwave-samplers if installed, else numpy
# --------------------------------------------------------------------------
@dataclass
class AnnealResult:
    route: Optional[list]
    cost: Optional[float]
    wall_time: float
    feasible_reads: int
    num_reads: int
    sweeps: int
    implementation: str             # "dwave-samplers" | "numpy"
    truncated: bool = False         # numpy path hit its time cap before all sweeps


def _try_neal():
    try:
        from dwave.samplers import SimulatedAnnealingSampler
        return SimulatedAnnealingSampler(), "dwave-samplers"
    except Exception:
        pass
    try:
        from neal import SimulatedAnnealingSampler
        return SimulatedAnnealingSampler(), "dwave-samplers"
    except Exception:
        return None, None


def run_annealer_sim(W, penalty_mult=10.0, num_reads=16, sweeps=400, seed=1,
                     max_seconds=60.0) -> AnnealResult:
    """Simulated annealing on the roadmap QUBO.  Returns best FEASIBLE tour only."""
    W = np.asarray(W, float)
    N = W.shape[0]
    Q, offset, _ = build_qubo(W, penalty=penalty_mult * float(W.max()))
    n = N * N

    sampler, impl = _try_neal()
    t0 = time.perf_counter()
    truncated = False
    if sampler is not None:
        import dimod
        bqm = dimod.BinaryQuadraticModel.from_qubo(Q, offset=offset)
        ss = sampler.sample(bqm, num_reads=num_reads, num_sweeps=sweeps, seed=seed)
        wall = time.perf_counter() - t0
        rows = [(dict(d.sample), d.energy) for d in ss.data(["sample", "energy"])]
        done = sweeps
    else:
        from sa_numpy import anneal
        X, E, done = anneal(Q, n, num_reads=num_reads, sweeps=sweeps, seed=seed,
                            max_seconds=max_seconds)
        wall = time.perf_counter() - t0
        truncated = done < sweeps
        rows = [({k: int(v) for k, v in enumerate(x)}, e + offset) for x, e in zip(X, E)]
        impl = "numpy"

    best, feasible = None, 0
    for sample, _e in rows:
        route, ok = decode_route(sample, N)
        if ok:
            feasible += 1
            c = route_cost(route, W)          # recompute from the route itself
            if best is None or c < best[1]:
                best = (route, c)
    return AnnealResult(best[0] if best else None, best[1] if best else None,
                        wall, feasible, num_reads, done, impl, truncated)


# --------------------------------------------------------------------------
# One benchmark row
# --------------------------------------------------------------------------
@dataclass
class Row:
    n: int
    qubo_bits: int
    exact_status: str                 # optimal | timeout | skipped_memory | not_run
    exact_time: Optional[float]
    exact_cost: Optional[float]
    heur_time: float
    heur_cost: float
    ann_time: Optional[float]
    ann_cost: Optional[float]
    ann_feasible: Optional[str]       # e.g. "9/16"
    ann_impl: Optional[str]
    ann_truncated: bool
    qpu_proj_time: Optional[float]    # None where pure QPU cannot embed the problem
    pure_qpu_fits: bool
    hybrid_min_time: float
    ref_cost: float                   # best known: exact if available else best of others
    ref_is_exact: bool
    note: str = ""

    def gap(self, cost):
        if cost is None or self.ref_cost <= 0:
            return None
        return 100.0 * (cost - self.ref_cost) / self.ref_cost


def benchmark_one(n, n_threats=3, gamma=10.0, seed=42, exact_timeout=15.0,
                  max_memory_gb=1.0, run_annealer=True, anneal_reads=16,
                  anneal_sweeps=400, anneal_max_seconds=60.0, penalty_mult=10.0,
                  qpu=QPUModel()) -> Row:
    m = generate_mission(n, n_threats, gamma=gamma, seed=seed)
    ex = solve_classical_route(m.W, timeout=exact_timeout, max_memory_gb=max_memory_gb)
    he = solve_heuristic_route(m.W)

    ann = (run_annealer_sim(m.W, penalty_mult, anneal_reads, anneal_sweeps, seed + 1,
                            anneal_max_seconds) if run_annealer else None)

    costs = [c for c in (ex.cost, he.cost, ann.cost if ann else None) if c is not None]
    ref = min(costs)
    fits = n <= qpu.max_nodes_pure_qpu()
    return Row(
        n=n, qubo_bits=n * n,
        exact_status=ex.status,
        exact_time=ex.exec_time if ex.status == "optimal" else None,
        exact_cost=ex.cost,
        heur_time=he.exec_time, heur_cost=he.cost,
        ann_time=ann.wall_time if ann else None,
        ann_cost=ann.cost if ann else None,
        ann_feasible=f"{ann.feasible_reads}/{ann.num_reads}" if ann else None,
        ann_impl=ann.implementation if ann else None,
        ann_truncated=ann.truncated if ann else False,
        qpu_proj_time=qpu.access_seconds() if fits else None,
        pure_qpu_fits=fits,
        hybrid_min_time=hybrid_min_time_limit_s(n * n),
        ref_cost=ref, ref_is_exact=ex.cost is not None,
        note=ex.note,
    )


def run_benchmark(sizes, progress=None, **kw):
    rows = []
    for i, n in enumerate(sizes):
        rows.append(benchmark_one(n, **kw))
        if progress:
            progress(i + 1, len(sizes), rows[-1])
    return rows


# --------------------------------------------------------------------------
# Extrapolating the exact solver past where it could be run
# --------------------------------------------------------------------------
def fit_held_karp(rows, min_time=0.005):
    """
    Fit  t = c * N^2 * 2^N  to measured exact times (least squares on log t).
    Returns (c, n_points_used) or (None, 0) if there are too few usable points.
    Points below `min_time` seconds are ignored (timer noise / numpy overhead).
    """
    pts = [(r.n, r.exact_time) for r in rows
           if r.exact_status == "optimal" and r.exact_time and r.exact_time >= min_time]
    if len(pts) < 2:
        return None, 0
    n = np.array([p[0] for p in pts], float)
    t = np.array([p[1] for p in pts], float)
    log_c = np.mean(np.log(t) - np.log(n ** 2 * 2.0 ** n))
    return float(np.exp(log_c)), len(pts)


def extrapolate_held_karp(c, n):
    return c * n ** 2 * 2.0 ** n


def human_time(s):
    if s is None:
        return "-"
    if s < 1e-3:
        return f"{s * 1e6:.0f} us"
    if s < 1:
        return f"{s * 1e3:.1f} ms"
    if s < 120:
        return f"{s:.2f} s"
    if s < 86400 * 2:
        return f"{s / 3600:.1f} h" if s >= 7200 else f"{s / 60:.1f} min"
    if s < 86400 * 365 * 2:
        return f"{s / 86400:.1f} days"
    return f"{s / (86400 * 365):.1e} years"


def rows_to_dicts(rows):
    return [asdict(r) for r in rows]


def rows_from_dicts(ds):
    return [Row(**d) for d in ds]
