"""Fixed drone map and exact line-segment/circle threat checks."""

from dataclasses import dataclass
from itertools import permutations
from math import hypot

NODES = ((0.0, 0.0), (0.0, 4.0), (4.0, 4.0), (4.0, 0.0))
THREAT_CENTER = (2.0, 2.0)
THREAT_RADIUS = 0.6
DEFAULT_UNSAFE_PENALTY = 10_000.0


@dataclass(frozen=True)
class RouteMap:
    nodes: tuple[tuple[float, float], ...]
    threat_center: tuple[float, float]
    threat_radius: float
    unsafe_penalty: float
    distances: tuple[tuple[float, ...], ...]
    unsafe_edges: tuple[tuple[bool, ...], ...]
    costs: tuple[tuple[float, ...], ...]


def segment_intersects_circle(start, end, center, radius):
    """Include touching the boundary and either endpoint inside the circle."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return hypot(start[0] - center[0], start[1] - center[1]) <= radius
    projection = ((center[0] - start[0]) * dx + (center[1] - start[1]) * dy)
    fraction = max(0.0, min(1.0, projection / length_squared))
    nearest = (start[0] + fraction * dx, start[1] + fraction * dy)
    return hypot(nearest[0] - center[0], nearest[1] - center[1]) <= radius


def make_map(unsafe_penalty=DEFAULT_UNSAFE_PENALTY):
    if unsafe_penalty < 0:
        raise ValueError("unsafe_penalty must be nonnegative")
    distances = tuple(
        tuple(hypot(a[0] - b[0], a[1] - b[1]) for b in NODES) for a in NODES
    )
    unsafe_edges = tuple(
        tuple(i != j and segment_intersects_circle(a, b, THREAT_CENTER, THREAT_RADIUS)
              for j, b in enumerate(NODES))
        for i, a in enumerate(NODES)
    )
    costs = tuple(
        tuple(distances[i][j] + unsafe_penalty * unsafe_edges[i][j]
              for j in range(len(NODES)))
        for i in range(len(NODES))
    )
    route_map = RouteMap(NODES, THREAT_CENTER, THREAT_RADIUS, unsafe_penalty,
                         distances, unsafe_edges, costs)
    if not any(route_is_safe((0, *order, 0), route_map) for order in permutations((1, 2, 3))):
        raise ValueError("No safe complete tour exists")
    return route_map


def route_is_safe(route, route_map):
    return all(not route_map.unsafe_edges[a][b] for a, b in zip(route, route[1:]))


def route_cost(route, route_map):
    if len(route) != len(route_map.nodes) + 1 or route[0] != 0 or route[-1] != 0:
        raise ValueError("Route must start and end at depot and visit every node")
    if set(route[:-1]) != set(range(len(route_map.nodes))):
        raise ValueError("Route must visit each node exactly once")
    return sum(route_map.costs[a][b] for a, b in zip(route, route[1:]))


def exact_tours(route_map):
    return sorted(
        ((route_cost(route, route_map), route, route_is_safe(route, route_map))
         for order in permutations(range(1, len(route_map.nodes)))
         for route in [(0, *order, 0)]),
        key=lambda item: (item[0], item[1]),
    )
