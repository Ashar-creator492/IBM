"""Position-assignment TSP QUBO and local two-layer QAOA."""

from dataclasses import dataclass
from time import perf_counter

import numpy as np
from qiskit.circuit.library import qaoa_ansatz
from qiskit.primitives import StatevectorEstimator, StatevectorSampler
from qiskit_optimization import QuadraticProgram
from qiskit_optimization.converters import QuadraticProgramToQubo
from scipy.optimize import minimize

from .qiskit_map import route_cost, route_is_safe


def variable_index(node, position):
    return 4 * node + position


def build_problem(route_map):
    """All four positions are variables; the cyclic objective includes the return edge."""
    program = QuadraticProgram("threat_aware_four_node_tsp")
    for node in range(4):
        for position in range(4):
            program.binary_var(name=f"x_{node}_{position}")
    quadratic = {}
    for position in range(4):
        next_position = (position + 1) % 4
        for source in range(4):
            for destination in range(4):
                if source != destination:
                    pair = (f"x_{source}_{position}", f"x_{destination}_{next_position}")
                    quadratic[pair] = route_map.costs[source][destination]
    program.minimize(quadratic=quadratic)
    for node in range(4):
        program.linear_constraint(
            linear={f"x_{node}_{position}": 1 for position in range(4)},
            sense="==", rhs=1, name=f"visit_node_{node}",
        )
    for position in range(4):
        program.linear_constraint(
            linear={f"x_{node}_{position}": 1 for node in range(4)},
            sense="==", rhs=1, name=f"fill_position_{position}",
        )
    return program


def encode_route(route):
    if len(route) != 5 or route[0] != 0 or route[-1] != 0 or set(route[:-1]) != set(range(4)):
        raise ValueError("Expected a complete depot-first four-node tour")
    bits = [0] * 16
    for position, node in enumerate(route[:-1]):
        bits[variable_index(node, position)] = 1
    return bits


def decode_bits(bits, route_map):
    """Return (route, reason); route is None for an infeasible assignment."""
    if len(bits) != 16 or any(bit not in (0, 1) for bit in bits):
        return None, "not a 16-bit binary assignment"
    positions = []
    for position in range(4):
        assigned = [node for node in range(4) if bits[variable_index(node, position)]]
        if len(assigned) != 1:
            return None, f"position {position} has {len(assigned)} nodes"
        positions.append(assigned[0])
    if len(set(positions)) != 4:
        return None, "a node is visited more than once"
    depot_position = positions.index(0)
    ordered = positions[depot_position:] + positions[:depot_position]
    return (0, *ordered[1:], 0), None


def bitstring_to_bits(bitstring):
    # Qiskit prints classical bit 15 on the left and bit 0 on the right.
    return [int(bit) for bit in reversed(bitstring.replace(" ", ""))]


@dataclass
class QAOAResult:
    qubits: int
    circuit_depth: int
    iterations: int
    objective: float
    ising_offset: float
    parameters: tuple[float, ...]
    success: bool
    message: str
    elapsed_seconds: float
    shots: int
    counts: dict[str, int]
    sampled_bitstring: str
    sampled_route: tuple[int, ...] | None
    sampled_reason: str | None
    sampled_cost: float | None
    sampled_safe: bool | None
    feasible_samples: int
    best_feasible_bitstring: str | None
    best_feasible_route: tuple[int, ...] | None
    best_feasible_cost: float | None
    best_feasible_safe: bool | None
    history: list[float]
    layers: int
    circuit_text: str


def run_qaoa(route_map, maxiter=12, shots=4096, seed=7, penalty=1000.0, layers=2):
    if maxiter < 1 or shots < 1:
        raise ValueError("maxiter and shots must be positive")
    started = perf_counter()
    program = build_problem(route_map)
    qubo = QuadraticProgramToQubo(penalty=penalty).convert(program)
    hamiltonian, offset = qubo.to_ising()
    circuit = qaoa_ansatz(hamiltonian, reps=layers)
    estimator = StatevectorEstimator()
    rng = np.random.default_rng(seed)
    initial = rng.uniform(0.0, np.pi, len(circuit.parameters))
    history = []

    def expectation(parameters):
        result = estimator.run([(circuit, hamiltonian, parameters)]).result()[0]
        value = float(result.data.evs)
        history.append(value + float(offset))
        return value

    optimized = minimize(expectation, initial, method="COBYLA",
                         options={"maxiter": maxiter, "rhobeg": 0.5})
    measured = circuit.copy()
    measured.measure_all()
    sampler = StatevectorSampler(seed=seed)
    counts = sampler.run([(measured, optimized.x)], shots=shots).result()[0].data.meas.get_counts()
    most_common = max(counts, key=lambda bitstring: (counts[bitstring], bitstring))
    sampled_route, sampled_reason = decode_bits(bitstring_to_bits(most_common), route_map)
    sampled_cost = route_cost(sampled_route, route_map) if sampled_route else None
    sampled_safe = route_is_safe(sampled_route, route_map) if sampled_route else None

    feasible = []
    for bitstring, count in counts.items():
        route, _ = decode_bits(bitstring_to_bits(bitstring), route_map)
        if route is not None:
            feasible.append((route_cost(route, route_map), -count, bitstring,
                             route, route_is_safe(route, route_map)))
    best = min(feasible) if feasible else None
    return QAOAResult(
        circuit.num_qubits, circuit.depth(), int(optimized.nfev), float(optimized.fun),
        float(offset), tuple(float(value) for value in optimized.x),
        bool(optimized.success), str(optimized.message), perf_counter() - started,
        shots, counts, most_common, sampled_route, sampled_reason, sampled_cost,
        sampled_safe, sum(-item[1] for item in feasible),
        best[2] if best else None, best[3] if best else None,
        best[0] if best else None, best[4] if best else None,
        history, layers, str(circuit.assign_parameters(optimized.x).draw(output="text", fold=160)),
    )
