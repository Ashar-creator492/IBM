"""
quantum_solver.py  --  Q-Route D-Wave Quantum Engine  (roadmap Hour 6-9)

Pipeline (roadmap §4 Block 2 + §7 risk matrix):
    QUBO dict -> dimod BQM -> sampler -> best FEASIBLE sample -> route

Backends
    "qpu"       EmbeddingComposite(DWaveSampler())   (roadmap snippet, num_reads=100)
    "hybrid"    LeapHybridSampler (BQM)              ("hybrid sampler for large scale")
    "simulator" local simulated annealing (neal)     (roadmap fail-safe)

If a hardware backend raises ANY exception (no network, bad token, embedding
failure, ...), the engine falls back to local simulated annealing, as required
by roadmap §4 Hour 21-23 and §7.  The result records that this happened so the
UI can label timings honestly.
"""
import math
import time
from dataclasses import dataclass
from typing import Optional

import dimod

from qubo_builder import decode_route


@dataclass
class QuantumResult:
    route: Optional[list]        # node order, or None if no feasible sample found
    valid: bool                  # True if `route` satisfies all QUBO constraints
    energy: float                # energy of the returned sample (best feasible if any)
    qpu_time: Optional[float]    # seconds. Real QPU access time on hardware;
                                 # local sampling wall time if timing_is_qpu is False
    wall_time: float             # total seconds spent in sampler.sample()
    backend: str                 # backend that actually produced the result
    fallback_used: bool          # True if hardware failed and simulator was used
    fallback_reason: Optional[str]
    timing_is_qpu: bool          # False => qpu_time is NOT QPU time (do not present it as such)


def _simulated_sampler():
    try:
        from neal import SimulatedAnnealingSampler          # roadmap: neal
    except ImportError:                                      # neal is now a shim of dwave-samplers
        from dwave.samplers import SimulatedAnnealingSampler
    return SimulatedAnnealingSampler()


def _sample_hardware(bqm, backend, num_reads, label, time_limit):
    # Imported lazily so the simulator path works even if dwave-system is absent.
    if backend == "qpu":
        from dwave.system import DWaveSampler, EmbeddingComposite
        sampler = EmbeddingComposite(DWaveSampler())
        return sampler.sample(bqm, num_reads=num_reads, label=label)
    if backend == "hybrid":
        from dwave.system import LeapHybridSampler
        sampler = LeapHybridSampler()
        kwargs = {"label": label}
        if time_limit is not None:
            kwargs["time_limit"] = time_limit
        return sampler.sample(bqm, **kwargs)
    raise ValueError(f"Unknown hardware backend: {backend!r}")


def _qpu_access_seconds(info):
    """qpu_access_time is reported in microseconds (roadmap: / 1e6)."""
    t = info.get("timing", {}).get("qpu_access_time")   # direct QPU
    if t is None:
        t = info.get("qpu_access_time")                  # hybrid solver
    return t / 1e6 if t is not None else None


def _best_feasible(sampleset, N):
    """Lowest-energy sample that decodes to a valid route (no silent repair)."""
    for datum in sampleset.data(["sample", "energy"], sorted_by="energy"):
        route, ok = decode_route(datum.sample, N)
        if ok:
            return route, True, datum.energy
    return None, False, sampleset.first.energy


def solve_quantum_route_full(Q_dict, offset=0.0, backend="qpu", num_reads=100,
                             label="Q-Route Engine", time_limit=None):
    """Full-detail solve. Returns a QuantumResult."""
    variables = {u for key in Q_dict for u in key}
    N = math.isqrt(len(variables))
    if N * N != len(variables):
        raise ValueError(f"QUBO has {len(variables)} variables; expected N^2")

    bqm = dimod.BinaryQuadraticModel.from_qubo(Q_dict, offset=offset)

    sampleset, used, fallback_reason, timing_is_qpu = None, backend, None, False
    wall = 0.0

    if backend in ("qpu", "hybrid"):
        try:
            t0 = time.perf_counter()
            sampleset = _sample_hardware(bqm, backend, num_reads, label, time_limit)
            wall = time.perf_counter() - t0
            timing_is_qpu = True
        except Exception as exc:                              # roadmap §7 fail-safe
            fallback_reason = f"{type(exc).__name__}: {exc}"
            sampleset, used = None, "simulator"
    elif backend == "simulator":
        pass
    else:
        raise ValueError(f"backend must be 'qpu', 'hybrid' or 'simulator', got {backend!r}")

    if sampleset is None:                                     # simulator or fallback
        used = "simulator"
        t0 = time.perf_counter()
        sampleset = _simulated_sampler().sample(bqm, num_reads=num_reads)
        wall = time.perf_counter() - t0

    route, valid, energy = _best_feasible(sampleset, N)

    qpu_time = _qpu_access_seconds(sampleset.info) if timing_is_qpu else None
    if qpu_time is None:                                      # no QPU timing available
        timing_is_qpu = False
        qpu_time = wall

    return QuantumResult(route, valid, energy, qpu_time, wall, used,
                         fallback_reason is not None, fallback_reason, timing_is_qpu)


def solve_quantum_route(Q_dict, offset=0.0, backend="qpu", num_reads=100):
    """
    Roadmap-signature wrapper:  returns (route, energy, qpu_time).
    Use solve_quantum_route_full() when you also need backend / fallback info.
    """
    r = solve_quantum_route_full(Q_dict, offset=offset, backend=backend,
                                 num_reads=num_reads)
    return r.route, r.energy, r.qpu_time
