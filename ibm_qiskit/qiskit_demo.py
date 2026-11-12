"""Run the complete local IBM Qiskit track demonstration."""

import argparse

from .qiskit_map import exact_tours, make_map
from .qiskit_qaoa import run_qaoa


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maxiter", type=int, default=12)
    parser.add_argument("--shots", type=int, default=4096)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--unsafe-penalty", type=float, default=10_000.0)
    args = parser.parse_args()

    route_map = make_map(args.unsafe_penalty)
    print("Nodes (0 is depot):")
    for index, coordinate in enumerate(route_map.nodes):
        print(f"  {index}: {coordinate}")
    print(f"Threat: center={route_map.threat_center}, radius={route_map.threat_radius}")
    print("Threat-aware cost matrix:")
    for row in route_map.costs:
        print("  " + " ".join(f"{value:10.3f}" for value in row))

    optimum_cost, optimum_route, optimum_safe = exact_tours(route_map)[0]
    print(f"Classical exact optimum (6 depot-first tours): {optimum_route}, "
          f"cost={optimum_cost:.3f}, safe={optimum_safe}")

    result = run_qaoa(route_map, maxiter=args.maxiter, shots=args.shots, seed=args.seed)
    print(f"QAOA: qubits={result.qubits}, layers=2, circuit_depth={result.circuit_depth}")
    print(f"COBYLA: evaluations={result.iterations}/{args.maxiter}, "
          f"success={result.success}, Ising expectation={result.objective:.3f}, "
          f"QUBO expectation={result.objective + result.ising_offset:.3f}")
    print("Optimized parameters: " + ", ".join(f"{value:.4f}" for value in result.parameters))
    print(f"COBYLA message: {result.message}")
    print(f"QAOA execution time: {result.elapsed_seconds:.3f} s")
    print(f"Samples: {result.shots} shots, {len(result.counts)} distinct bitstrings, "
          f"{result.feasible_samples} feasible shots")
    print(f"Most frequent sampled bitstring: {result.sampled_bitstring} "
          f"({result.counts[result.sampled_bitstring]} shots)")
    if result.sampled_route:
        print(f"Most frequent sample: FEASIBLE route={result.sampled_route}, "
              f"cost={result.sampled_cost:.3f}, threat-safe={result.sampled_safe}")
    else:
        print(f"Most frequent sample: INFEASIBLE ({result.sampled_reason})")
    if result.best_feasible_route:
        print(f"Best feasible QAOA sample: bitstring={result.best_feasible_bitstring}, "
              f"route={result.best_feasible_route}, cost={result.best_feasible_cost:.3f}, "
              f"threat-safe={result.best_feasible_safe}, "
              f"classically-optimal={abs(result.best_feasible_cost - optimum_cost) < 1e-9}")
    else:
        print("QAOA found no feasible sampled route; classical optimum above is comparison only.")


if __name__ == "__main__":
    main()
