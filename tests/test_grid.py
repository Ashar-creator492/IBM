from math import isclose
import pytest
from fastapi.testclient import TestClient
from api.main import app
from ibm_qiskit.grid import build_grid
from ibm_qiskit.qiskit_map import exact_tours, segment_intersects_circle
from ibm_qiskit.qiskit_qaoa import build_problem, encode_route, decode_bits

@pytest.mark.parametrize('size',[24,40,64])
def test_grid_paths_and_costs(size):
    route_map, grid = build_grid(size)
    blocked = set(map(tuple,grid['obstacles']+grid['danger']))
    for pair in grid['pairs']:
        path = pair['path']
        assert path[0] == grid['nodes'][pair['source']]
        assert path[-1] == grid['nodes'][pair['target']]
        assert not blocked.intersection(path)
        assert set(path) <= set(pair['explored'])
        for a,b in zip(path,path[1:]):
            assert abs(a[0]-b[0])+abs(a[1]-b[1]) == 1
            def world(c): return ((c[0]-3)*grid['step'], (size-4-c[1])*grid['step'])
            assert not segment_intersects_circle(world(a),world(b),(2,2),.6)
        assert isclose(pair['cost'],(len(path)-1)*grid['step'])
        assert pair['cost'] == route_map.costs[pair['source']][pair['target']]
    problem = build_problem(route_map)
    for cost,route,safe in exact_tours(route_map):
        assert safe
        bits=encode_route(route)
        assert decode_bits(bits,route_map)[0] == route
        assert isclose(problem.objective.evaluate(bits),cost)


def test_grid_api_real_solver():
    client=TestClient(app)
    assert client.get('/api/grid?size=12').status_code == 422
    grid=client.get('/api/grid').json()
    response=client.post('/api/grid/run',json={'shots':4096,'maxiter':40,'layers':2,'seed':7})
    assert response.status_code == 200
    data=response.json()
    assert data['qubits'] == 16
    assert data['best_feasible_route'] is not None
    route=data['best_feasible_route']
    assert route[0] == route[-1] == 0
    assert sorted(route[:-1]) == [0,1,2,3]
    expected=sum(grid['map']['costs'][a][b] for a,b in zip(route,route[1:]))
    assert isclose(data['best_feasible_cost'],expected)
    assert data['best_feasible_safe']


def test_unreachable_grid_is_explicit(monkeypatch):
    from dataclasses import replace
    import ibm_qiskit.grid as module
    base = module.make_map()
    monkeypatch.setattr(module, 'make_map', lambda: replace(base, threat_radius=10))
    with pytest.raises(ValueError, match='No safe grid path'):
        module.build_grid()

@pytest.mark.parametrize('size',[24,40,64])
def test_corridors_and_ew_force_detours(size):
    _, grid = build_grid(size)
    assert all(0 < x < size-1 and 0 < y < size-1 for x,y in grid['nodes'])
    assert len({x for x,y in grid['nodes']}) >= 3
    assert any(len(p['path'])-1 > abs(p['path'][0][0]-p['path'][-1][0])+abs(p['path'][0][1]-p['path'][-1][1]) for p in grid['pairs'])
    _, without_ew = build_grid(size,exclude_ew=False)
    assert any(p['cost'] > q['cost'] for p,q in zip(grid['pairs'],without_ew['pairs']))
    blocked=set(map(tuple,grid['obstacles']+grid['danger']))
    for pair in grid['pairs']:
        frontier={pair['explored'][0]}
        settled=set()
        assert len(pair['frontier_steps']) == len(pair['explored'])
        for cell,added in zip(pair['explored'],pair['frontier_steps']):
            assert cell in frontier
            frontier.remove(cell)
            settled.add(cell)
            for neighbor in added:
                assert neighbor not in blocked
                assert neighbor not in settled
                assert abs(cell[0]-neighbor[0])+abs(cell[1]-neighbor[1]) == 1
                frontier.add(neighbor)


def test_original_modes_are_preserved():
    from ibm_qiskit.qiskit_map import make_map, NODES
    original=make_map()
    assert original.nodes == NODES
    assert exact_tours(original)[0][0] == 16
    m,g=build_grid(scenario='regression')
    assert g['nodes'] == [(3,36),(3,3),(36,3),(36,36)]
    assert exact_tours(m)[0][0] == 16
