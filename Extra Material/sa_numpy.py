"""
sa_numpy.py -- minimal pure-numpy simulated annealing for a QUBO.

Used by benchmark.run_annealer_sim ONLY when dwave-samplers / neal is not
installed. It is a plain single-spin-flip Metropolis annealer run on all reads
in parallel. It is a CLASSICAL algorithm; its time is CPU time.

If the requested sweeps would exceed `max_seconds`, the number of sweeps is
reduced and the temperature schedule is compressed to fit (so the run still
ends cold). The sweeps actually used are returned so the UI can say so.
"""
import time

import numpy as np


def _schedule(M, S):
    """Geometric beta range from the coefficient scale (hot: accept most moves)."""
    nz = np.abs(M[M != 0])
    big = float(np.max(np.abs(S).sum(axis=1) + np.abs(np.diag(M)))) or 1.0
    small = float(nz.min()) if nz.size else 1.0
    beta_hot = np.log(2.0) / big * 4.0          # a few big moves still accepted
    beta_cold = np.log(100.0) / small           # smallest coefficient is "frozen"
    return beta_hot, max(beta_cold, beta_hot * 10)


def anneal(Q, n, num_reads=16, sweeps=400, seed=1, max_seconds=60.0):
    """
    Returns (X, E, sweeps_done): X (num_reads, n) 0/1 samples, E their energies
    WITHOUT the constant offset, and the number of sweeps actually run.
    """
    M = np.zeros((n, n))
    for (u, v), c in Q.items():
        M[u, v] += c
    diag = np.diag(M).copy()
    S = M + M.T
    np.fill_diagonal(S, 0.0)                    # symmetric off-diagonal couplings

    rng = np.random.default_rng(seed)
    X = rng.integers(0, 2, size=(num_reads, n)).astype(float)
    H = X @ S                                   # local fields, shape (reads, n)
    b_hot, b_cold = _schedule(M, S)

    def run_sweep(beta):
        nonlocal H
        for i in rng.permutation(n):
            dE = (1.0 - 2.0 * X[:, i]) * (diag[i] + H[:, i])
            acc = (dE <= 0) | (rng.random(num_reads) < np.exp(-np.clip(beta * dE, -50, 50)))
            if acc.any():
                dx = np.where(acc, 1.0 - 2.0 * X[:, i], 0.0)
                X[:, i] += dx
                H += np.outer(dx, S[i])

    # time the first (hot) sweep to decide how many sweeps fit in the budget
    t0 = time.perf_counter()
    run_sweep(b_hot)
    per_sweep = max(time.perf_counter() - t0, 1e-6)
    total = int(max(5, min(sweeps, max_seconds / per_sweep)))
    betas = np.geomspace(b_hot, b_cold, total)
    for beta in betas[1:]:
        run_sweep(beta)

    E = np.einsum("ri,ij,rj->r", X, M, X)
    return X.astype(int), E, total
