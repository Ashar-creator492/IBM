from copy import deepcopy
from dataclasses import replace
from math import isclose
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from api.main import app
from ibm_qiskit.grid import build_grid
from ibm_qiskit.qiskit_map import segment_intersects_circle
from ibm_qiskit.qiskit_qaoa import run_qaoa

client=TestClient(app)

def mission():
    return dict(size=24,revision=1,nodes=[[4,4],[18,4],[18,18],[4,18]],obstacles=[],
                zones=[dict(center=[11.5,11.5],radius=2)],pathfinding='dijkstra')

def validate(env):
    r=client.post('/api/mission/validate',json=env)
    assert r.status_code==200,r.text
    return r.json()

def test_moving_checkpoint_changes_cost_and_revision():
    a=mission();b=deepcopy(a);b['revision']=2;b['nodes'][1]=[17,8]
    first,second=validate(a),validate(b)
    assert first['feasible'] and second['feasible']
    assert second['revision']==2
    assert first['grid']['map']['costs'] != second['grid']['map']['costs']
    assert second['grid']['nodes'][1] == [17,8]

@pytest.mark.parametrize('placement',[[4,4],[11,11],[-1,2],[24,2]])
def test_invalid_checkpoint_placement(placement):
    env=mission();env['nodes'][1]=placement
    response=client.post('/api/mission/validate',json=env)
    assert response.status_code==422 or not response.json()['feasible']

def test_wall_and_enclosure_impossible_and_recovery_skips_solver():
    env=mission();wall=[[10,y] for y in range(24)];env['obstacles']=wall
    invalid=validate(env)
    assert not invalid['feasible'] and invalid['unavailable_connections']
    with patch('api.main.run_qaoa') as solver:
        result=client.post('/api/mission/run',json={'environment':env,'config':{}}).json()
        assert result['result'] is None and result['status']=='No feasible route'
        solver.assert_not_called()
    env['obstacles']=[];env['revision']=2
    assert validate(env)['feasible']
    env['obstacles']=[[17,18],[19,18],[18,17],[18,19]]
    assert not validate(env)['feasible']
    env['obstacles']=[]
    assert validate(env)['feasible']

def test_ew_conservative_occupancy_growth_multiple_zones_and_paths():
    env=mission();a=validate(env)['grid']
    env['zones'][0]['radius']=4
    b=validate(env)['grid']
    assert len(b['danger'])>len(a['danger'])
    env['zones'].append(dict(center=[7,7],radius=1.1))
    grid=validate(env)['grid'];blocked=set(map(tuple,grid['obstacles']+grid['danger']))
    for pair in grid['pairs']:
        path=pair['path'];assert not blocked.intersection(map(tuple,path))
        assert isclose(pair['cost'],(len(path)-1)*grid['step'])
        for u,v in zip(path,path[1:]):
            assert abs(u[0]-v[0])+abs(u[1]-v[1])==1
            assert not any(segment_intersects_circle(u,v,z['center'],z['radius']) for z in env['zones'])
    env['zones']=[dict(center=[10,10],radius=2)];env['nodes'][1]=[12,11]
    assert not validate(env)['feasible'] # Center outside disk, but cell square intersects it.
    env=mission();env['zones'][0]['radius']=20
    assert not validate(env)['feasible']

def test_obstacles_force_recomputed_path_lengths():
    env=mission();before=validate(env)['grid']['map']['costs']
    env['obstacles']=[[10,y] for y in range(0,12)]
    after=validate(env)['grid']['map']['costs']
    assert after[0][1]>before[0][1]


def test_custom_cost_matrix_reaches_real_qaoa_and_no_sample_is_distinct():
    env=mission();env['nodes'][1]=[17,8];env['revision']=9
    expected=validate(env)['grid']['map']['costs']
    with patch('api.main.run_qaoa',wraps=run_qaoa) as solver:
        response=client.post('/api/mission/run',json={'environment':env,'config':{'maxiter':40}})
        assert response.status_code==200,response.text
        result=response.json();route_map=solver.call_args.args[0]
        assert [list(row) for row in route_map.costs]==expected
        assert result['revision']==9 and result['feasible']
        r=result['result'];route=r['best_feasible_route']
        if route:
            assert route[0]==route[-1]==0 and set(route[:-1])==set(range(4))
            assert r['best_feasible_safe']
            assert isclose(r['best_feasible_cost'],sum(expected[a][b] for a,b in zip(route,route[1:])))
    # Preserve the real quantum metadata but force the legitimate no-sample branch.
    actual=run_qaoa(route_map,maxiter=8,shots=128)
    missing=replace(actual,best_feasible_route=None,best_feasible_cost=None,best_feasible_safe=None,
                    best_feasible_bitstring=None,feasible_samples=0)
    with patch('api.main.run_qaoa',return_value=missing):
        result=client.post('/api/mission/run',json={'environment':env,'config':{}}).json()
        assert result['feasible'] and result['status']=='No feasible QAOA sample'
        assert result['result']['best_feasible_route'] is None
