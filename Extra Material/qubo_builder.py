"""
qubo_builder.py  --  Q-Route QUBO matrix converter  (roadmap Hour 4-6)

Translates a threat-weighted distance matrix W into the QUBO of roadmap §2.4:

    H_total = H_cost + λ1·H_node_visit + λ2·H_position_step + λ3·H_depot

Binary variable x[i, p] = 1  <=>  node i is visited at step p   (§2.3)
Flat variable index:  u = i * N + p                              (N^2 variables)

Pure Python + numpy only (no D-Wave imports), so it can be tested offline.
"""
import numpy as np


def var_index(i, p, N):
    """Flat QUBO variable id for x[i, p]."""
    return i * N + p


def _add(Q, u, v, coeff):
    """Accumulate coeff into Q[(u, v)] using sorted (upper-triangular) keys."""
    key = (u, v) if u <= v else (v, u)
    Q[key] = Q.get(key, 0.0) + coeff


def _add_exactly_one(Q, variables, lam):
    """
    Expand  lam * (sum_k x_k - 1)^2  for binary x  (x^2 = x):
        = lam * ( -sum_k x_k + 2*sum_{k<l} x_k x_l + 1 )
    Returns the constant offset (lam).
    """
    for a, u in enumerate(variables):
        _add(Q, u, u, -lam)                       # linear term
        for v in variables[a + 1:]:
            _add(Q, u, v, 2.0 * lam)              # pairwise term
    return lam


def build_qubo(W, penalty=None):
    """
    Build the QUBO dictionary for the threat-aware routing problem.

    Parameters
    ----------
    W : (N, N) array-like
        Edge weights W_ij = d_ij * (1 + γ·Σ_k I(i, j, t_k))   (§2.2).
        Node 0 is the depot.
    penalty : float, optional
        Value used for λ1 = λ2 = λ3.  Default: 10 * max(W_ij), as set in the
        roadmap's risk table (§7).

    Returns
    -------
    Q : dict[(u, v)] -> coefficient   (upper-triangular, ready for
        dimod.BinaryQuadraticModel.from_qubo)
    offset : float
        Constant energy term dropped by the QUBO dict.  Pass it to
        from_qubo(..., offset=offset) so that energies equal the real
        H_total (a valid tour then has energy == its weighted length).
    lam : float
        The penalty value actually used.
    """
    W = np.asarray(W, dtype=float)
    if W.ndim != 2 or W.shape[0] != W.shape[1]:
        raise ValueError("W must be a square (N, N) matrix")
    N = W.shape[0]
    if N < 2:
        raise ValueError("Need at least 2 nodes (depot + one target)")

    lam = float(penalty) if penalty is not None else 10.0 * float(W.max())
    if lam <= 0:
        raise ValueError("Penalty must be > 0 (is W all zeros?)")

    Q = {}
    offset = 0.0

    # 1. H_cost = Σ_p Σ_i Σ_j W_ij · x[i,p] · x[j,(p+1) mod N]
    #    i == j terms are skipped (W_ii = 0 since d_ii = 0).
    for p in range(N):
        q = (p + 1) % N
        for i in range(N):
            for j in range(N):
                if i != j and W[i, j] != 0.0:
                    _add(Q, var_index(i, p, N), var_index(j, q, N), W[i, j])

    # 2. H_node_visit: every node i appears exactly once  (λ1)
    for i in range(N):
        offset += _add_exactly_one(
            Q, [var_index(i, p, N) for p in range(N)], lam)

    # 3. H_position_step: every step p holds exactly one node  (λ2)
    for p in range(N):
        offset += _add_exactly_one(
            Q, [var_index(i, p, N) for i in range(N)], lam)

    # 4. H_depot = (x[0,0] - 1)^2 = 1 - x[0,0]   (λ3)
    _add(Q, var_index(0, 0, N), var_index(0, 0, N), -lam)
    offset += lam

    return Q, offset, lam


def decode_route(sample, N):
    """
    Turn a {variable: 0/1} sample into a node sequence.

    Returns (route, is_valid).
    is_valid is True only if every step has exactly one node, every node is
    used exactly once, and step 0 is the depot (node 0).
    If invalid, route is None -- an infeasible sample is NOT silently repaired.
    """
    route = []
    for p in range(N):
        nodes = [i for i in range(N) if sample.get(var_index(i, p, N), 0) == 1]
        if len(nodes) != 1:
            return None, False
        route.append(nodes[0])
    if len(set(route)) != N or route[0] != 0:
        return None, False
    return route, True


def route_cost(route, W):
    """Total weighted length of the closed tour (includes return to depot)."""
    W = np.asarray(W, dtype=float)
    n = len(route)
    return float(sum(W[route[k], route[(k + 1) % n]] for k in range(n)))
