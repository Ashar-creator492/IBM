"""Thin HTTP boundary around the tested IBM solver."""
from dataclasses import asdict
from threading import Lock
from time import perf_counter
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ibm_qiskit.qiskit_map import make_map, exact_tours
from ibm_qiskit.grid import build_grid
from ibm_qiskit.qiskit_qaoa import run_qaoa, decode_bits, bitstring_to_bits

app = FastAPI(title="Q-Route IBM Quantum Lab")
solver_lock = Lock()


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunRequest(Model):
    shots: int = Field(default=4096, ge=128, le=16384, strict=True)
    maxiter: int = Field(default=12, ge=8, le=80, strict=True)
    layers: int = Field(default=2, ge=1, le=3, strict=True)
    seed: int = Field(default=7, ge=0, le=2**32 - 1, strict=True)


class Health(Model):
    status: str
    simulator: str


class MapResponse(Model):
    nodes: list[list[float]]
    threat_center: list[float]
    threat_radius: float
    unsafe_penalty: float
    costs: list[list[float]]
    unsafe_edges: list[list[bool]]


class ClassicalResponse(Model):
    route: list[int]
    cost: float
    safe: bool
    elapsed_seconds: float
    tours_evaluated: int


class Sample(Model):
    bitstring: str
    count: int
    feasible: bool
    reason: str | None


class RunResponse(Model):
    qubits: int
    circuit_depth: int
    iterations: int
    objective: float
    ising_offset: float
    parameters: list[float]
    success: bool
    message: str
    elapsed_seconds: float
    shots: int
    sampled_bitstring: str
    sampled_route: list[int] | None
    sampled_reason: str | None
    sampled_cost: float | None
    sampled_safe: bool | None
    feasible_samples: int
    best_feasible_bitstring: str | None
    best_feasible_route: list[int] | None
    best_feasible_cost: float | None
    best_feasible_safe: bool | None
    history: list[float]
    layers: int
    circuit_text: str
    top_samples: list[Sample]
    matched_optimum: bool


@app.get('/api/health', response_model=Health)
def health():
    return dict(status="ready", simulator="Qiskit Statevector / local CPU")


@app.get('/api/map', response_model=MapResponse)
def get_map():
    data = asdict(make_map())
    data.pop('distances')
    return data


@app.get('/api/classical', response_model=ClassicalResponse)
def classical():
    route_map = make_map()
    started = perf_counter()
    tours = exact_tours(route_map)
    elapsed = perf_counter() - started
    cost, route, safe = tours[0]
    return dict(route=route, cost=cost, safe=safe, elapsed_seconds=elapsed, tours_evaluated=len(tours))


@app.post('/api/qaoa/run', response_model=RunResponse)
def optimize(request: RunRequest):
    return solve(request, make_map())


def solve(request, route_map):
    # Sync routes run in FastAPI's thread pool; health/map remain responsive.
    if not solver_lock.acquire(blocking=False):
        raise HTTPException(409, "A simulation is already running. Please wait.")
    try:
        result = run_qaoa(route_map, **request.model_dump())
        data = asdict(result)
        counts = data.pop('counts')
        data['top_samples'] = []
        for bitstring, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]:
            route, reason = decode_bits(bitstring_to_bits(bitstring), route_map)
            data['top_samples'].append(dict(bitstring=bitstring, count=count,
                                            feasible=route is not None, reason=reason))
        data['matched_optimum'] = (result.best_feasible_cost is not None
            and abs(result.best_feasible_cost - exact_tours(route_map)[0][0]) < 1e-9)
        return data
    except Exception as error:
        logging.exception("Local QAOA simulation failed")
        raise HTTPException(500, "Local simulation failed. Check the backend terminal and retry.") from error
    finally:
        solver_lock.release()


@app.get('/api/grid')
def grid(size: int = 40, scenario: str = "demo"):
    try:
        route_map, data = build_grid(size, scenario)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    data['map'] = asdict(route_map)
    cost, route, safe = exact_tours(route_map)[0]
    started = perf_counter()
    tours = exact_tours(route_map)
    data['classical'] = dict(route=route,cost=cost,safe=safe,
        elapsed_seconds=perf_counter()-started,tours_evaluated=len(tours))
    return data


@app.post('/api/grid/run', response_model=RunResponse)
def optimize_grid(request: RunRequest, size: int = 40, scenario: str = "demo"):
    try:
        route_map, _ = build_grid(size, scenario)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return solve(request, route_map)

# Editable missions retain exactly four node/position assignments (16 variables).
from typing import Literal, Annotated
from pydantic import model_validator

CellCoordinate = Annotated[int, Field(strict=True, ge=0, le=63)]

class Zone(Model):
    center: tuple[Annotated[float, Field(ge=0, le=63)], Annotated[float, Field(ge=0, le=63)]]
    radius: float = Field(gt=0, le=64)

class MissionEnvironment(Model):
    size: int = Field(ge=24, le=64, strict=True)
    revision: int = Field(ge=0, strict=True)
    nodes: list[tuple[CellCoordinate, CellCoordinate]] = Field(min_length=4,max_length=4)
    obstacles: list[tuple[CellCoordinate, CellCoordinate]] = Field(max_length=4096)
    zones: list[Zone] = Field(max_length=4)
    pathfinding: Literal['dijkstra'] = 'dijkstra'

    @model_validator(mode='after')
    def finite_zones(self):
        import math
        if any(not math.isfinite(z.radius) or any(not math.isfinite(v) for v in z.center) for z in self.zones):
            raise ValueError('Zone values must be finite')
        return self

class MissionRun(Model):
    environment: MissionEnvironment
    config: RunRequest


def evaluate_environment(environment):
    try:
        route_map, data = build_grid(environment.size, environment=environment.model_dump())
    except ValueError as error:
        return None, dict(feasible=False,revision=environment.revision,
                          status='No feasible route',message=str(error),grid=None,unavailable_connections=getattr(error,'unavailable_connections',[]))
    started=perf_counter()
    tours=exact_tours(route_map)
    cost,route,safe=tours[0]
    data['map']=asdict(route_map)
    data['classical']=dict(route=route,cost=cost,safe=safe,
                           elapsed_seconds=perf_counter()-started,tours_evaluated=len(tours))
    return route_map,dict(feasible=True,revision=environment.revision,
                         status='Mission ready',message='All four checkpoints connected',grid=data)

@app.post('/api/mission/validate')
def validate_mission(environment: MissionEnvironment):
    return evaluate_environment(environment)[1]

@app.post('/api/mission/run')
def run_mission(request: MissionRun):
    route_map, validation = evaluate_environment(request.environment)
    if route_map is None:
        return {**validation,'result':None}
    result = solve(request.config,route_map)
    # Every decoded tour uses only prevalidated, safe navigable pair paths.
    return {**validation,'status': 'Mission ready' if result['best_feasible_route'] else
            'No feasible QAOA sample', 'result':result}
