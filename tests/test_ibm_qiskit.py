from itertools import permutations

import pytest
from qiskit_optimization.converters import QuadraticProgramToQubo

from ibm_qiskit.qiskit_map import (
    exact_tours, make_map, route_cost, route_is_safe, segment_intersects_circle,
)
from ibm_qiskit.qiskit_qaoa import (
    bitstring_to_bits, build_problem, decode_bits, encode_route,
)


def test_threat_geometry_and_map():
    route_map = make_map()
    assert len(route_map.nodes) == 4
    assert route_map.unsafe_edges[0][2] and route_map.unsafe_edges[1][3]
    assert not route_map.unsafe_edges[0][1]
    assert segment_intersects_circle((0, 0), (4, 4), (2, 2), 0.6)
    assert not segment_intersects_circle((0, 0), (0, 4), (2, 2), 0.6)
    assert all(route_map.costs[i][j] == route_map.costs[j][i]
               for i in range(4) for j in range(4))
    assert route_map.costs[0][2] == pytest.approx(4 * 2**0.5 + 10_000)
    assert route_cost((0, 1, 2, 3, 0), route_map) == pytest.approx(16)
    assert route_is_safe((0, 1, 2, 3, 0), route_map)
    assert not route_is_safe((0, 2, 1, 3, 0), route_map)
    assert make_map(123).costs[0][2] == pytest.approx(4 * 2**0.5 + 123)


def test_all_six_tours_and_closing_edge():
    route_map = make_map()
    tours = exact_tours(route_map)
    assert len(tours) == len(list(permutations((1, 2, 3)))) == 6
    assert tours[0][0] == pytest.approx(16)
    assert sum(safe for _, _, safe in tours) == 2
    assert route_cost((0, 1, 3, 2, 0), route_map) == pytest.approx(
        route_map.costs[0][1] + route_map.costs[1][3]
        + route_map.costs[3][2] + route_map.costs[2][0]
    )
    with pytest.raises(ValueError):
        route_cost((0, 1, 1, 3, 0), route_map)


def test_qubo_constraints_and_objective():
    route_map = make_map()
    program = build_problem(route_map)
    assert program.get_num_binary_vars() == 16
    assert len(program.linear_constraints) == 8
    qubo = QuadraticProgramToQubo(penalty=1000).convert(program)
    assert qubo.get_num_binary_vars() == 16
    assert len(qubo.linear_constraints) == 0
    hamiltonian, offset = qubo.to_ising()
    assert hamiltonian.num_qubits == 16
    assert isinstance(offset, float)
    for _, route, _ in exact_tours(route_map):
        bits = encode_route(route)
        assert program.is_feasible(bits)
        assert program.objective.evaluate(bits) == pytest.approx(route_cost(route, route_map))
        assert qubo.objective.evaluate(bits) == pytest.approx(route_cost(route, route_map))
    assert not program.is_feasible([0] * 16)
    assert qubo.objective.evaluate([0] * 16) > 16


def test_decode_and_bit_order():
    route_map = make_map()
    route = (0, 3, 2, 1, 0)
    bits = encode_route(route)
    assert decode_bits(bits, route_map) == (route, None)
    assert bitstring_to_bits("".join(map(str, reversed(bits)))) == bits
    # The unpinned assignment is cyclically equivalent and must still start at depot.
    shifted = [0] * 16
    for position, node in enumerate((3, 2, 1, 0)):
        shifted[4 * node + position] = 1
    assert decode_bits(shifted, route_map) == (route, None)
    invalid, reason = decode_bits([0] * 16, route_map)
    assert invalid is None and "position" in reason
    duplicated = encode_route(route)
    duplicated[4 * 2 + 2] = 0
    duplicated[4 * 3 + 2] = 1
    invalid, reason = decode_bits(duplicated, route_map)
    assert invalid is None and "more than once" in reason
