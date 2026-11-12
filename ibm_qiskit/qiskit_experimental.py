"""CLI for the separate six-location / 25-qubit fixed-depot experiment."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from qiskit_optimization.converters import QuadraticProgramToQubo
from .grid import build_grid
from .qiskit_map import exact_tours
from .qiskit_fixed import build_fixed_problem, run_fixed_qaoa, fixed_ansatz


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',choices=['GPU','CPU'],default='GPU')
    parser.add_argument('--maxiter',type=int,default=8)
    parser.add_argument('--shots',type=int,default=4096)
    parser.add_argument('--layers',type=int,default=1)
    parser.add_argument('--seed',type=int,default=7)
    parser.add_argument('--size',type=int,default=40)
    parser.add_argument('--model-only',action='store_true',help='Construct the actual circuit without simulation')
    parser.add_argument('--output',type=Path,help='Save actual result metadata and samples as JSON')
    args=parser.parse_args()
    route_map,grid=build_grid(args.size,'six')
    print('Experimental six-location mode: fixed depot, five targets, 25 assignment qubits.',flush=True)
    print('Classical grid search seconds:',grid['search_seconds'],flush=True)
    print('Pairwise grid costs:',route_map.costs,flush=True)
    exact=exact_tours(route_map)
    print('Exact classical optimum (120 tours):',exact[0],flush=True)
    if args.model_only:
        operator,offset=QuadraticProgramToQubo(penalty=1000).convert(build_fixed_problem(route_map)).to_ising()
        circuit=fixed_ansatz(operator,5,args.layers)
        print('Circuit constructed, NOT simulated:',circuit.num_qubits,'qubits;',len(circuit.parameters),'parameters; depth',circuit.depth())
        return
    print(f'Executing Aer {args.device}: {args.maxiter} evaluations, {args.layers} layers, {args.shots} shots. No fallback.',flush=True)
    try:
        result=run_fixed_qaoa(route_map,maxiter=args.maxiter,shots=args.shots,layers=args.layers,seed=args.seed,device=args.device)
    except (RuntimeError,ImportError) as error:
        parser.exit(2,f'Execution unavailable: {error}\n')
    data=asdict(result)
    data.update(simulator_device=args.device,formulation='fixed_depot',node_count=6,mixer='row_preserving_xy',
                grid_search_seconds=grid['search_seconds'],classical_optimum=exact[0],classical_tours=120)
    print('Actual solver seconds:',result.elapsed_seconds)
    print('Optimizer converged:',result.success,';',result.message)
    print('Feasible shots:',result.feasible_samples,'/',result.shots)
    print('Most frequent sample:',result.sampled_bitstring,'route:',result.sampled_route,'reason:',result.sampled_reason)
    print('Best feasible QAOA route:',result.best_feasible_route,'cost:',result.best_feasible_cost,'safe:',result.best_feasible_safe)
    if not result.best_feasible_route:
        print('No feasible QAOA sample found. The classical optimum has NOT been substituted.')
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(data,indent=2)+'\n')
        print('Saved actual result:',args.output)

if __name__=='__main__':
    main()
