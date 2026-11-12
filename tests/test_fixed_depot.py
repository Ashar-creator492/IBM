from dataclasses import replace
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from qiskit_optimization.converters import QuadraticProgramToQubo
from api.main import app
from ibm_qiskit.grid import build_grid
from ibm_qiskit.qiskit_map import exact_tours,route_cost
from ibm_qiskit.qiskit_fixed import build_fixed_problem,encode_fixed_route,decode_fixed_bits,aer_backend,run_fixed_qaoa
from ibm_qiskit.qiskit_qaoa import bitstring_to_bits

@pytest.mark.parametrize('size',[24,40,64])
def test_six_grid_and_120_fixed_depot_tours(size):
    m,g=build_grid(size,'six');assert len(m.nodes)==6 and len(g['pairs'])==15
    blocked=set(map(tuple,g['obstacles']+g['danger']))
    for pair in g['pairs']:
        assert not blocked.intersection(pair['path'])
        assert pair['cost']==pytest.approx((len(pair['path'])-1)*g['step'])
    qp=build_fixed_problem(m);assert qp.get_num_binary_vars()==25
    assert len(qp.linear_constraints)==10
    qubo=QuadraticProgramToQubo(penalty=1000).convert(qp)
    op,offset=qubo.to_ising();assert op.num_qubits==25
    tours=exact_tours(m);assert len(tours)==120
    for cost,route,safe in tours:
        bits=encode_fixed_route(route)
        assert qp.is_feasible(bits) and safe
        assert decode_fixed_bits(bits,m)==(route,None)
        assert bitstring_to_bits(''.join(map(str,reversed(bits))))==bits
        assert qp.objective.evaluate(bits)==pytest.approx(cost)
        assert qubo.objective.evaluate(bits)==pytest.approx(cost)
    assert decode_fixed_bits([0]*25,m)[0] is None
    assert decode_fixed_bits([1]*25,m)[0] is None
    assert decode_fixed_bits([0]*16,m)[0] is None
    # Verify Ising energy against the real cost without allocating a 25-qubit state.
    bits=encode_fixed_route(tours[0][1]);energy=offset
    for pauli,coefficient in op.to_list():
        energy+=coefficient.real*(-1)**sum(bits[i] for i,p in enumerate(reversed(pauli)) if p=='Z')
    assert energy==pytest.approx(tours[0][0])


def test_return_to_depot_changes_objective_and_unsafe_routes_rejected():
    m,_=build_grid(scenario='six');route=(0,1,2,3,4,5,0);bits=encode_fixed_route(route)
    matrix=[list(row) for row in m.costs];matrix[5][0]+=7
    changed=replace(m,costs=tuple(map(tuple,matrix)))
    assert build_fixed_problem(changed).objective.evaluate(bits)==pytest.approx(route_cost(route,m)+7)
    unsafe=[list(row) for row in m.unsafe_edges];unsafe[5][0]=True
    assert decode_fixed_bits(bits,replace(m,unsafe_edges=tuple(map(tuple,unsafe))))[0] is None


def test_gpu_is_never_silently_replaced_with_cpu():
    pytest.importorskip('qiskit_aer')
    with patch('qiskit_aer.AerSimulator') as simulator:
        simulator.return_value.available_devices.return_value=('CPU',)
        with pytest.raises(RuntimeError,match='No CPU fallback'):
            aer_backend('GPU')


def test_real_aer_cpu_primitives_on_small_fixed_depot_problem():
    pytest.importorskip('qiskit_aer')
    m,_=build_grid(scenario='six')
    small=replace(m,nodes=m.nodes[:3],costs=tuple(tuple(row[:3]) for row in m.costs[:3]),unsafe_edges=((False,)*3,)*3)
    r=run_fixed_qaoa(small,maxiter=8,shots=512,layers=1,device='CPU')
    assert r.qubits==4 and sum(r.counts.values())==512
    assert r.best_feasible_route is not None
    assert r.best_feasible_cost==pytest.approx(route_cost(r.best_feasible_route,small))


def test_experimental_api_matrix_revision_and_unavailable_gpu():
    c=TestClient(app);g=c.get('/api/grid?scenario=six').json();env=g['environment'];env['revision']=21
    v=c.post('/api/mission/validate',json=env).json()
    assert v['feasible'] and v['revision']==21 and v['grid']['classical']['tours_evaluated']==120
    assert len(v['grid']['map']['costs'])==6
    with patch('ibm_qiskit.qiskit_fixed.run_fixed_qaoa',side_effect=RuntimeError('GPU unavailable')) as solver:
        response=c.post('/api/mission/run',json={'environment':env,'config':{},'device':'GPU'})
        assert response.status_code==503 and 'GPU unavailable' in response.json()['detail']
        assert solver.call_args.kwargs['device']=='GPU'
        assert [list(row) for row in solver.call_args.args[0].costs]==v['grid']['map']['costs']
    env['nodes']=env['nodes'][:5]
    assert c.post('/api/mission/validate',json=env).status_code==422


def test_xy_mixer_preserves_rows_and_initial_state_is_not_a_classical_optimum():
    from qiskit.quantum_info import Statevector
    from qiskit import transpile
    from ibm_qiskit.qiskit_fixed import fixed_ansatz
    m,_=build_grid(scenario='six')
    small=replace(m,nodes=m.nodes[:4],costs=tuple(tuple(row[:4]) for row in m.costs[:4]),unsafe_edges=((False,)*4,)*4)
    op,_=QuadraticProgramToQubo(penalty=1000).convert(build_fixed_problem(small)).to_ising()
    circuit=fixed_ansatz(op,3,1)
    # Initial row-wise W states have 3^3 equiprobable assignments, only 3! feasible.
    initial=Statevector.from_instruction(circuit.assign_parameters([0,0]))
    probabilities=initial.probabilities_dict()
    assert sum(p>1e-10 for p in probabilities.values())==27
    assert sum(p for b,p in probabilities.items() if decode_fixed_bits(bitstring_to_bits(b),small)[0])==pytest.approx(6/27)
    evolved=Statevector.from_instruction(circuit.assign_parameters([.31,.77]))
    for bitstring,probability in evolved.probabilities_dict().items():
        if probability>1e-10:
            bits=bitstring_to_bits(bitstring)
            assert all(sum(bits[row*3:(row+1)*3])==1 for row in range(3))
