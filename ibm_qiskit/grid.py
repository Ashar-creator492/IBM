"""Deterministic airspace grid; Dijkstra paths supply the TSP edge costs."""
from dataclasses import replace
from heapq import heappop, heappush
from time import perf_counter
from .qiskit_map import make_map, segment_intersects_circle

class DisconnectedMission(ValueError):
    def __init__(self, source, target):
        super().__init__(f'No safe grid path between checkpoints {source:02d} and {target:02d}')
        self.unavailable_connections = [[source,target]]


def build_grid(size=40, scenario="demo", *, exclude_ew=True, environment=None):
    if not 24 <= size <= 64:
        raise ValueError('Grid size must be between 24 and 64')
    if scenario not in ("demo", "regression", "six"):
        raise ValueError("Unknown grid scenario")
    started = perf_counter()
    base = make_map()
    step = 4 / (size - 7)
    nodes = [(3, size-4), (3, 3), (size-4, 3), (size-4, size-4)]
    def world(cell):
        return ((cell[0]-3)*step, (size-4-cell[1])*step)
    if scenario in ("demo", "six"):
        nodes = [(round(x*(size-1)), round(y*(size-1)))
                 for x,y in [(0.15,.25),(.50,.30),(.50,.75),(.85,.65)]]
        # Two full-height baffles with staggered gates force a serpentine corridor.
        obstacles = {(x,y) for x in range(size) for y in range(size)
                     if (round(.29*size) <= x <= round(.32*size)
                         and not round(.70*size) <= y <= round(.85*size))
                     or (round(.67*size) <= x <= round(.70*size)
                         and not round(.15*size) <= y <= round(.30*size))}
    else:
        footprints = [(.17,.20,.28,.45),(.38,.12,.62,.22),
                      (.70,.30,.80,.60),(.23,.68,.48,.78),(.54,.77,.65,.89)]
        obstacles = {(x,y) for x in range(size) for y in range(size)
                     if any(a*size <= x <= c*size and b*size <= y <= d*size
                            for a,b,c,d in footprints)}
    if scenario == "six":
        nodes += [(round(.14*(size-1)),round(.79*(size-1))),
                  (round(.85*(size-1)),round(.20*(size-1)))]
    zones = [dict(center=[(size-1)/2]*2, radius=base.threat_radius/step)]
    if environment is not None:
        nodes = [tuple(c) for c in environment['nodes']]
        obstacles = {tuple(c) for c in environment['obstacles']}
        zones = environment['zones']
        if any(any(v < 0 or v >= size for v in z['center']) for z in zones):
            raise ValueError('Invalid configuration: EW center outside grid')
        if len(nodes) not in (4,6) or len(set(nodes)) != len(nodes):
            raise ValueError("Invalid configuration: exactly four or six distinct checkpoints required")
        if any(not (0 <= x < size and 0 <= y < size) for x,y in [*nodes,*obstacles]):
            raise ValueError("Invalid configuration: cells must be within grid bounds")
    # For editable missions block every cell whose square touches an EW circle.
    def danger_cell(x,y):
        margin = .5 if environment is not None else 0
        return any(max(abs(x-z['center'][0])-margin,0)**2 +
                   max(abs(y-z['center'][1])-margin,0)**2 <= z['radius']**2 for z in zones)
    danger = {(x,y) for x in range(size) for y in range(size) if danger_cell(x,y)}
    blocked = obstacles | (danger if exclude_ew else set())
    covered = [i for i,node in enumerate(nodes) if node in blocked]
    if covered:
        raise ValueError("No safe grid path: checkpoint(s) " + ', '.join(f'{i:02d}' for i in covered) + " covered by obstacles or EW exclusion")
    count=len(nodes)
    costs = [[0.0]*count for _ in range(count)]
    pairs = []
    for i in range(count):
        for j in range(i+1,count):
            source, target = nodes[i], nodes[j]
            queue, distance, parent, explored = [(0,source)], {source:0}, {}, []
            frontier = {source}
            frontier_steps = []
            while queue:
                cost, cell = heappop(queue)
                if cost != distance[cell]:
                    continue
                frontier.discard(cell)
                explored.append(cell)
                discovered = []
                if cell == target:
                    frontier_steps.append([])
                    break
                x,y = cell
                for neighbor in [(x+1,y),(x,y+1),(x-1,y),(x,y-1)]:
                    nx,ny = neighbor
                    if not (0 <= nx < size and 0 <= ny < size) or neighbor in blocked:
                        continue
                    if exclude_ew and any(segment_intersects_circle(cell,neighbor,z["center"],z["radius"]) for z in zones):
                        continue
                    candidate = cost+1
                    if candidate < distance.get(neighbor,float('inf')):
                        distance[neighbor] = candidate
                        parent[neighbor] = cell
                        heappush(queue,(candidate,neighbor))
                        if neighbor not in frontier:
                            frontier.add(neighbor)
                            discovered.append(neighbor)
                frontier_steps.append(discovered)
            if target not in distance:
                raise DisconnectedMission(i,j)
            path, cell = [target], target
            while cell != source:
                cell = parent[cell]
                path.append(cell)
            path.reverse()
            costs[i][j] = costs[j][i] = (len(path)-1)*step
            pairs.append(dict(source=i,target=j,path=path,explored=explored,frontier_steps=frontier_steps,cost=costs[i][j]))
    matrix = tuple(tuple(row) for row in costs)
    route_map = replace(base, nodes=tuple(world(node) for node in nodes), distances=matrix, costs=matrix,
                        unsafe_edges=tuple((False,)*count for _ in range(count)))
    data = dict(scenario=scenario,size=size,step=step,nodes=nodes,obstacles=sorted(obstacles),
                danger=sorted(danger),pairs=pairs,search_seconds=perf_counter()-started,
                threat_center=[(size-1)/2]*2,threat_radius=base.threat_radius/step)
    data['zones'] = zones
    data['environment'] = dict(size=size,revision=environment['revision'] if environment else 0,
                               nodes=nodes,obstacles=sorted(obstacles),zones=zones,pathfinding='dijkstra')
    return route_map,data
