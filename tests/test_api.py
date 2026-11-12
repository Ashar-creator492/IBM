from dataclasses import replace

from fastapi.testclient import TestClient
import pytest

from api import main
from ibm_qiskit.qiskit_map import make_map, route_cost, route_is_safe

client = TestClient(main.app)


@pytest.fixture(scope='module')
def result():
    return main.run_qaoa(make_map(), maxiter=12, shots=4096)


def test_health_map_and_classical():
    assert client.get('/api/health').json()['status'] == 'ready'
    data = client.get('/api/map').json()
    assert data['nodes'][0] == [0, 0]
    assert data['unsafe_edges'][0][2]
    exact = client.get('/api/classical').json()
    assert exact['cost'] == 16 and exact['safe'] and exact['tours_evaluated'] == 6


@pytest.mark.parametrize('body', [{'shots':0}, {'shots':'4096'}, {'layers':4}, {'maxiter':1000}, {'extra':1}])
def test_invalid_input(body):
    assert client.post('/api/qaoa/run', json=body).status_code == 422


def test_real_solver_response():
    response = client.post('/api/qaoa/run', json={})
    assert response.status_code == 200
    data = response.json()
    assert data['qubits'] == 16 and data['layers'] == 2
    assert len(data['history']) == data['iterations'] == 12
    assert data['circuit_text'] and data['top_samples']
    assert data['best_feasible_route'][0] == data['best_feasible_route'][-1] == 0
    assert data['best_feasible_cost'] == route_cost(data['best_feasible_route'], make_map())
    assert data['best_feasible_safe'] == route_is_safe(data['best_feasible_route'], make_map())
    assert data['success'] is False  # Bounded optimization, honestly reported.


def test_zero_feasible_and_unsafe_routes(monkeypatch, result):
    empty = replace(result, feasible_samples=0, best_feasible_route=None,
                    best_feasible_bitstring=None, best_feasible_cost=None, best_feasible_safe=None)
    monkeypatch.setattr(main, 'run_qaoa', lambda *a, **kw: empty)
    data = client.post('/api/qaoa/run', json={}).json()
    assert data['best_feasible_route'] is None and not data['matched_optimum']
    unsafe = replace(result, best_feasible_route=(0, 2, 1, 3, 0),
                     best_feasible_cost=20019.313708498987, best_feasible_safe=False)
    monkeypatch.setattr(main, 'run_qaoa', lambda *a, **kw: unsafe)
    data = client.post('/api/qaoa/run', json={}).json()
    assert data['best_feasible_safe'] is False and not data['matched_optimum']


def test_simulator_failure_and_busy(monkeypatch):
    def fail(*a, **kw):
        raise RuntimeError('test simulator failure')
    monkeypatch.setattr(main, 'run_qaoa', fail)
    assert client.post('/api/qaoa/run', json={}).status_code == 500
    assert not main.solver_lock.locked()
    main.solver_lock.acquire()
    try:
        assert client.post('/api/qaoa/run', json={}).status_code == 409
    finally:
        main.solver_lock.release()
