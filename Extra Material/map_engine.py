"""
map_engine.py -- synthetic map + EW threat zones + weight matrix  (roadmap Hour 2-4)

    W_ij = d_ij * (1 + γ * Σ_k I(i, j, t_k))                      (roadmap §2.2)

I(i, j, t_k) in [0, 1] = fraction of segment (i, j) lying inside threat circle k.
Node 0 is the depot (roadmap §2.1). Coordinates live on a 100 x 100 km grid.

Intersection methods
    "analytic"  exact line-circle maths (numpy only)           <- default, tested
    "shapely"   shapely.geometry.LineString ∩ Point.buffer(r)  <- roadmap's named
                tool; buffer() is a polygon approximation of the circle, so values
                differ from analytic by a small amount (<~1% of the radius).
"""
from dataclasses import dataclass

import numpy as np

GRID_KM = 100.0


@dataclass
class Mission:
    coords: np.ndarray          # (N, 2)  node 0 = depot
    threat_centers: np.ndarray  # (K, 2)
    threat_radii: np.ndarray    # (K,)
    gamma: float
    dist: np.ndarray            # (N, N) Euclidean distance d_ij
    W: np.ndarray               # (N, N) threat-weighted cost

    @property
    def n(self):
        return len(self.coords)


def _circle_interval(p, q, center, radius):
    """Parameter interval [t1, t2] (within [0, 1]) where p + t(q-p) is inside the circle, or None."""
    p, q, c = (np.asarray(v, dtype=float) for v in (p, q, center))
    d = q - p
    seg_len2 = float(d @ d)
    if seg_len2 == 0.0:
        return (0.0, 1.0) if np.linalg.norm(p - c) <= radius else None
    # Solve |p + t d - c|^2 = r^2 for t, then clip to [0, 1].
    f = p - c
    a, b, cc = seg_len2, 2.0 * float(f @ d), float(f @ f) - radius ** 2
    disc = b * b - 4 * a * cc
    if disc <= 0.0:
        return None
    root = np.sqrt(disc)
    t1 = max(0.0, (-b - root) / (2 * a))
    t2 = min(1.0, (-b + root) / (2 * a))
    return (t1, t2) if t2 > t1 else None


def segment_fraction_in_circle(p, q, center, radius):
    """Exact fraction (0..1) of segment p->q lying inside the circle."""
    iv = _circle_interval(p, q, center, radius)
    return 0.0 if iv is None else iv[1] - iv[0]


def segment_fraction_in_circle_shapely(p, q, center, radius, quad_segs=64):
    """Same quantity via shapely (needs shapely>=2.0)."""
    from shapely.geometry import LineString, Point
    line = LineString([tuple(p), tuple(q)])
    if line.length == 0.0:
        return 1.0 if Point(center).distance(Point(p)) <= radius else 0.0
    zone = Point(tuple(center)).buffer(radius, quad_segs=quad_segs)
    return float(line.intersection(zone).length / line.length)


def build_weight_matrix(coords, centers, radii, gamma, method="analytic"):
    """Return (dist, W). W is symmetric with a zero diagonal."""
    fn = {"analytic": segment_fraction_in_circle,
          "shapely": segment_fraction_in_circle_shapely}.get(method)
    if fn is None:
        raise ValueError("method must be 'analytic' or 'shapely'")
    n = len(coords)
    dist = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=2)
    W = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            frac = sum(fn(coords[i], coords[j], c, r) for c, r in zip(centers, radii))
            W[i, j] = W[j, i] = dist[i, j] * (1.0 + gamma * frac)
    return dist, W


def generate_mission(n_targets, n_threats, radius_range=(8.0, 15.0), gamma=10.0,
                     seed=42, method="analytic", depot=None, zones=None):
    """
    n_targets = N total nodes (node 0 = depot), as in the roadmap's "Number of
    Target Nodes (N)". Targets uniform in [10, 90]^2; threat centres uniform in
    [20, 80]^2; radii uniform in radius_range  (ranges from roadmap §6.2 code).

    depot : optional (x, y) in km. Overrides node 0's position; every other node is
            drawn exactly as before, so a given seed gives the same targets/zones.
    zones : optional list of (x, y, radius) in km. Replaces the random EW zones
            (n_threats and radius_range are then ignored).

    NOTE: the roadmap says γ >> 1 but gives no number. `gamma` is a free
    parameter (default 10 is a placeholder, not a value from the roadmap).
    """
    if n_targets < 2:
        raise ValueError("need at least 2 nodes")
    rng = np.random.default_rng(seed)
    coords = rng.uniform(10, 90, size=(n_targets, 2))
    centers = rng.uniform(20, 80, size=(n_threats, 2))
    radii = rng.uniform(radius_range[0], radius_range[1], size=n_threats)
    if depot is not None:
        coords[0] = np.clip(np.asarray(depot, dtype=float), 0.0, GRID_KM)
    if zones is not None:
        z = np.asarray(zones, dtype=float).reshape(-1, 3)
        centers, radii = z[:, :2].copy(), z[:, 2].copy()
    dist, W = build_weight_matrix(coords, centers, radii, gamma, method)
    return Mission(coords, centers, radii, gamma, dist, W)


def _union_fraction(p, q, centers, radii):
    """Exact fraction of segment inside the UNION of all threat circles."""
    ivs = sorted(iv for iv in (_circle_interval(p, q, c, r)
                               for c, r in zip(centers, radii)) if iv)
    total, cur_s, cur_e = 0.0, None, None
    for a, b in ivs:
        if cur_e is None or a > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = a, b
        else:
            cur_e = max(cur_e, b)
    if cur_e is not None:
        total += cur_e - cur_s
    return total


def route_threat_stats(route, mission):
    """
    Threat exposure of a closed tour (returns to depot).
    edges_in_threat : edges that enter at least one threat zone
    km_in_threat    : ground distance flown inside the union of threat zones
                      (overlaps are not double counted; note W in the QUBO uses
                      the SUM of per-zone fractions, as written in roadmap §2.2)
    km_total        : total ground distance
    """
    n = len(route)
    edges, km_in, km_total = 0, 0.0, 0.0
    for k in range(n):
        i, j = route[k], route[(k + 1) % n]
        frac = _union_fraction(mission.coords[i], mission.coords[j],
                               mission.threat_centers, mission.threat_radii)
        km_total += mission.dist[i, j]
        km_in += mission.dist[i, j] * frac
        edges += frac > 0.0
    return {"edges_in_threat": int(edges), "km_in_threat": float(km_in),
            "km_total": float(km_total)}
