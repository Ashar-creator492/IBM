"""Experimental fixed-depot QAOA: six locations require 5 x 5 = 25 qubits."""
from time import perf_counter
import numpy as np
from qiskit import transpile, QuantumCircuit
from qiskit.quantum_info import SparsePauliOp
from qiskit.circuit.library import qaoa_ansatz
from qiskit_optimization import QuadraticProgram
from qiskit_optimization.converters import QuadraticProgramToQubo
from scipy.optimize import minimize
from .qiskit_map import route_cost, route_is_safe
from .qiskit_qaoa import QAOAResult, bitstring_to_bits


def build_fixed_problem(route_map):
    targets = len(route_map.nodes)-1
    if not 1 <= targets <= 5:
        raise ValueError('Fixed-depot mode supports 2 to 6 total locations')
    qp = QuadraticProgram('fixed_depot_tsp')
    for node in range(1, targets+1):
        for position in range(targets):
            qp.binary_var(f'x_{node}_{position}')
    linear, quadratic = {}, {}
    for node in range(1, targets+1):
        # Both terms are required, including the single-target case.
        first, last = f'x_{node}_0', f'x_{node}_{targets-1}'
        linear[first] = linear.get(first,0)+route_map.costs[0][node]
        linear[last] = linear.get(last,0)+route_map.costs[node][0]
    for p in range(targets-1):
        for a in range(1, targets+1):
            for b in range(1, targets+1):
                if a != b:
                    quadratic[(f'x_{a}_{p}',f'x_{b}_{p+1}')] = route_map.costs[a][b]
    qp.minimize(linear=linear,quadratic=quadratic)
    for node in range(1, targets+1):
        qp.linear_constraint({f'x_{node}_{p}':1 for p in range(targets)},'==',1,f'visit_{node}')
    for p in range(targets):
        qp.linear_constraint({f'x_{node}_{p}':1 for node in range(1,targets+1)},'==',1,f'position_{p}')
    return qp


def encode_fixed_route(route):
    targets = len(route)-2
    if targets<1 or route[0]!=0 or route[-1]!=0 or set(route[1:-1])!=set(range(1,targets+1)):
        raise ValueError('Expected a complete fixed-depot tour')
    bits=[0]*(targets*targets)
    for p,node in enumerate(route[1:-1]):
        bits[(node-1)*targets+p]=1
    return bits


def decode_fixed_bits(bits, route_map):
    targets=len(route_map.nodes)-1
    if len(bits)!=targets*targets or any(b not in (0,1) for b in bits):
        return None,f'not a {targets*targets}-bit binary assignment'
    order=[]
    for p in range(targets):
        assigned=[node for node in range(1,targets+1) if bits[(node-1)*targets+p]]
        if len(assigned)!=1:
            return None,f'position {p} has {len(assigned)} targets'
        order.append(assigned[0])
    if len(set(order))!=targets:
        return None,'a target is visited more than once'
    route=(0,*order,0)
    if not route_is_safe(route,route_map):
        return None,'tour uses an unavailable or unsafe grid connection'
    return route,None


def aer_backend(device='GPU', seed=7):
    if device not in ('CPU','GPU'):
        raise ValueError('Choose CPU or GPU explicitly')
    try:
        from qiskit_aer import AerSimulator
    except ImportError as error:
        raise RuntimeError('Install requirements-aer.txt for CPU, or requirements-gpu.txt on CUDA Linux for GPU') from error
    probe=AerSimulator()
    if device not in probe.available_devices():
        raise RuntimeError(f'{device} unavailable in this Aer installation. Available: {probe.available_devices()}. No CPU fallback was used.')
    options=dict(method='statevector',device=device,precision='double',seed_simulator=seed,
                 max_parallel_threads=4,max_parallel_experiments=1,max_memory_mb=4096)
    return AerSimulator(**options),options


def fixed_ansatz(hamiltonian, targets, layers):
    """One excitation per target row; column uniqueness remains an energy constraint."""
    initial=QuantumCircuit(targets*targets)
    terms=[]
    for node in range(targets):
        row=[node*targets+p for p in range(targets)]
        # Prepare W(targets) without a dense state-preparation vector.
        initial.x(row[0])
        for p in range(targets-1):
            initial.cry(2*np.arccos(1/np.sqrt(targets-p)),row[p],row[p+1])
            initial.cx(row[p+1],row[p])
        pairs=[(row[p],row[p+1]) for p in range(targets-1)]
        if targets>2:
            pairs.append((row[-1],row[0]))
        for a,b in pairs:
            # Adjacent XX/YY factors together preserve the row excitation number.
            terms.extend([('XX',[a,b],.5),('YY',[a,b],.5)])
    mixer=SparsePauliOp.from_sparse_list(terms,num_qubits=targets*targets) if terms else SparsePauliOp.from_list([('I'*(targets*targets),0)])
    return qaoa_ansatz(hamiltonian,reps=layers,initial_state=initial,mixer_operator=mixer)


def run_fixed_qaoa(route_map,maxiter=8,shots=4096,seed=7,penalty=1000.0,layers=1,device='GPU'):
    if maxiter<1 or shots<1 or layers<1:
        raise ValueError('Positive evaluations, shots and layers required')
    started=perf_counter()
    backend,options=aer_backend(device,seed)
    from qiskit_aer.primitives import EstimatorV2, SamplerV2
    qp=build_fixed_problem(route_map)
    qubo=QuadraticProgramToQubo(penalty=penalty).convert(qp)
    hamiltonian,offset=qubo.to_ising()
    circuit=transpile(fixed_ansatz(hamiltonian,len(route_map.nodes)-1,layers),backend,optimization_level=1,seed_transpiler=seed)
    observable=hamiltonian.apply_layout(circuit.layout) if circuit.layout else hamiltonian
    estimator=EstimatorV2(options={'backend_options':options,'default_precision':0.0})
    sampler=SamplerV2(seed=seed,options={'backend_options':options})
    history=[]
    def expectation(parameters):
        value=float(estimator.run([(circuit,observable,parameters)]).result()[0].data.evs)
        history.append(value+float(offset))
        return value
    initial=np.random.default_rng(seed).uniform(0,np.pi,len(circuit.parameters))
    optimized=minimize(expectation,initial,method='COBYLA',options={'maxiter':maxiter,'rhobeg':.5})
    measured=circuit.copy();measured.measure_all()
    counts=sampler.run([(measured,optimized.x)],shots=shots).result()[0].data.meas.get_counts()
    most_common=max(counts,key=lambda b:(counts[b],b))
    sampled,reason=decode_fixed_bits(bitstring_to_bits(most_common),route_map)
    feasible=[]
    for bitstring,count in counts.items():
        route,_=decode_fixed_bits(bitstring_to_bits(bitstring),route_map)
        if route is not None:
            feasible.append((route_cost(route,route_map),-count,bitstring,route,True))
    best=min(feasible) if feasible else None
    return QAOAResult(circuit.num_qubits,circuit.depth(),int(optimized.nfev),float(optimized.fun),
        float(offset),tuple(float(v) for v in optimized.x),bool(optimized.success),str(optimized.message),
        perf_counter()-started,shots,counts,most_common,sampled,reason,
        route_cost(sampled,route_map) if sampled else None,True if sampled else None,
        sum(-v[1] for v in feasible),best[2] if best else None,best[3] if best else None,
        best[0] if best else None,best[4] if best else None,history,layers,
        str(circuit.assign_parameters(optimized.x).draw(output='text',fold=160)))
