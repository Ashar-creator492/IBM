# Q/ROUTE - IBM Qiskit Mission Lab

An interactive, local demonstration of quantum-assisted drone route planning.
Move delivery checkpoints, draw restricted airspace, and configure electronic
warfare (EW) zones. The application computes safe grid paths, uses QAOA to choose
a visiting order, and compares the sampled result with an exact classical answer.

**IBM track:** one drone, one depot, three delivery checkpoints, 16 binary
variables, and 16 simulated qubits. No IBM account, API key, paid service, or
physical quantum processor is required. D-Wave is not part of this implementation.

## Quick start for judges

Download/extract this repository, or clone it using the repository's **Code** URL.
Open a terminal in the project root: the folder containing `requirements-api.txt`,
`api/`, `ibm_qiskit/`, and `frontend/`.

### Prerequisites

- **Python 3.13** and its `venv` module.
- **Node.js 24** with npm.
- Internet for the initial dependency installation. Simulation then runs locally.
- Two terminal windows: one for FastAPI and one for the React frontend.

Tested on macOS / Apple Silicon with Python **3.13.15** and Node.js **24.21.0**.
Windows commands are provided below; Windows and Linux have not been separately
verified. Use the tested versions for the most reproducible setup. Python 3.9
from an older system installation will not work with the pinned dependency set.

### 1. Install Python and frontend dependencies

**macOS / Linux**, from the project root:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-api.txt
npm --prefix frontend ci
```

**Windows PowerShell**, from the project root:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
npm.cmd --prefix frontend ci
```

Virtual-environment activation is not required: these commands call its Python
executable directly. `requirements-api.txt` includes `requirements-ibm.txt`, so
**Qiskit and all solver dependencies are installed by the same command**.
Do not install additional or unpinned Qiskit packages separately.

The Python requirements pin:

| Package | Version | Purpose |
| --- | --- | --- |
| Qiskit | 2.6.2 | Quantum circuits, Ising conversion support, local primitives |
| Qiskit Optimization | 0.7.0 | QuadraticProgram and QUBO conversion |
| SciPy | 1.18.1 | COBYLA parameter optimization |
| FastAPI | 0.162.5 | Validated local HTTP API |
| Uvicorn | 0.54.0 | API server |

Pytest and the API test client dependency are also included. React, TypeScript,
Vite, Tailwind, icons, and fonts install from `frontend/package-lock.json` through
`npm ci`. No separate Aer, IBM Runtime, or cloud service setup is needed.

### 2. Start the backend - terminal 1

Keep this terminal in the **project root**.

macOS / Linux:

```sh
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Wait for `Application startup complete`. Interactive API documentation:
**http://127.0.0.1:8000/docs**. Health check:
**http://127.0.0.1:8000/api/health**.

### 3. Start the frontend - terminal 2

From another terminal in the **project root**:

```sh
npm --prefix frontend run dev
```

On Windows PowerShell, use `npm.cmd` in place of `npm` if script execution policy
blocks `npm.ps1`.

Open **http://127.0.0.1:5173**. If Vite prints a different local port because 5173
is occupied, open the printed URL instead. Vite forwards `/api` requests to the
backend on port 8000. **Keep both terminals running.** Stop them with Ctrl+C.

## Suggested judging walkthrough

1. Open **Route Lab** using the navigation or **Explore Route Lab**.
2. Keep the corridor mission at **40 x 40**, **4,096 shots**, **40 COBYLA max
   evaluations**, and **2 QAOA layers**. Wait for connectivity validation.
3. Click **Run Optimization**. Watch recorded classical Dijkstra exploration,
   actual QAOA execution, then the drone's flight if a feasible sample is found.
4. Inspect the decoded tour, safe grid route, cost, qubits, circuit depth,
   convergence status, and exact classical comparison. Open **Analysis** for
   sampled bitstrings, feasible-shot percentage, expectation history, and the
   actual bound Qiskit circuit.
5. Use **Replay Search**, **Replay Flight**, pause/resume, and speed controls.
   Blue cells are explored; sand cells form the frontier; lime marks the selected
   flight path. Replay does not rerun QAOA.
6. With **Select / Move**, drag a checkpoint or EW circle. Change the EW radius,
   draw obstacles, or erase cells. The previous solution disappears immediately;
   costs and connectivity are recalculated. Run QAOA again for the edited mission.
7. Demonstrate failure: on the default 40 x 40 mission, draw a thin rectangle
   across the entire grid at row **y = 18**, without covering checkpoints. This
   divides the mission into disconnected regions. Expect **NO FEASIBLE ROUTE**,
   an explanation, no green flight, and no quantum optimization.
8. Click **Reset Environment**, wait for validation, and run again to demonstrate
   recovery. The **Original corner grid - regression** preset is also available.

A previous verified default edited-mission run returned `00 -> 01 -> 03 -> 02 -> 00`
with safe cost **18.181818**, matching the exact optimum. This is an observed
example, not a promised result for every environment, platform, or parameter set.

## Editor and playback controls

| Control | Behavior |
| --- | --- |
| Select / Move | Drag depot 00, checkpoints 01-03, or an EW circle; checkpoints snap to cells |
| Pan, zoom, Fit | Navigate the grid without changing the environment |
| Draw cells / Draw rectangle | Create real blocked cells or walls |
| Erase / Clear obstacles | Restore navigable cells / remove all obstacles |
| Add EW / Remove zone | Add up to four EW circles or remove the selected circle |
| EW X, Y, radius | Edit the selected zone in grid-cell coordinates |
| Restore checkpoints / Reset EW zones | Restore the loaded preset's positions or zones |
| Undo / Redo | Restore up to 50 intermediate editing states |
| Reset Environment | Restore the loaded demonstration preset |
| Reset simulation | Discard the result and stop playback; keep the edited environment |

Checkpoint overlap and placement in blocked cells are rejected. EW changes that
cover a checkpoint are explicitly flagged as invalid. Whole rectangles are not
draggable; erase and redraw them. Editing is locked while a solver run is active.
Editing during flight cancels playback and invalidates the solution. Edits are
in-memory and do not persist through browser refresh.

## How Qiskit fits into the project

```text
React mission editor
  -> FastAPI validates the environment and revision
  -> Dijkstra computes safe paths for all six checkpoint pairs
  -> Path lengths become a shared travel-cost matrix
  -> QuadraticProgram: 4 nodes x 4 tour positions = 16 binary variables
  -> Eight one-hot constraints become QUBO penalties
  -> QUBO converts to an Ising Hamiltonian
  -> QAOA circuit alternates cost and mixer operations
  -> SciPy COBYLA tunes circuit angles using StatevectorEstimator
  -> StatevectorSampler draws final bitstrings
  -> Decode assignments, validate tours, and compare with exact enumeration
  -> Concatenate the corresponding grid paths and animate one drone
```

**Classical pathfinding chooses paths; QAOA chooses the visiting order.** Grid
cells are not qubits. Two QAOA layers have four adjustable angles. The grid size
does not change the 16-variable quantum formulation.

- **COBYLA evaluations:** objective-evaluation budget for tuning circuit angles.
  The frontend defaults to 40; the original CLI and bare API config default to 12.
- **Shots:** final sampled outcomes, default 4,096. Parameter tuning uses exact
  statevector expectations; it does not take 4,096 shots at every evaluation.
- **Layers:** alternating QAOA cost/mixer blocks, default 2; supported UI range 1-3.
  Layers are different from gate-level circuit depth.
- **History:** QUBO expectation including assignment penalties, not the cost of a
  single route. Assignment violations carry a 1,000-unit squared penalty.
- **Seed:** default 7 for repeatable parameter initialization and sampling within
  the same software setup.

Grid movement is orthogonal; each step costs `4 / (size - 7)` units. Editable
missions conservatively block every cell square touching an EW circle and check
path segments geometrically. Both quantum and classical comparisons use the
current environment's grid-path matrix, including travel back to the depot.

## Interpreting results honestly

| Result | Meaning |
| --- | --- |
| No feasible route | Classical validation proves a blocked or disconnected mission; QAOA is skipped |
| No feasible QAOA sample | The environment is reachable, but sampling found no valid assignment |
| Optimizer converged | COBYLA met its stopping criteria; this does not prove global optimality |
| Matches exact optimum | The best feasible sampled cost matches enumeration of all six depot-first orders |
| Simulated flight complete | Drone playback has returned to the depot; separate from computation completion |

The most frequent bitstring can be infeasible. The app reports it separately from
the best feasible sampled tour. No classical answer is substituted as a QAOA
result. More shots, layers, or evaluations do not guarantee feasibility or optimality.

All quantum circuits run in a **local CPU simulator**, not physical IBM hardware.
For four nodes, exact enumeration is tiny; this project makes **no quantum speedup
claim**. Grid-search time, QAOA computation time, and animation duration are
reported separately. Classical enumeration and QAOA timing cover different work
and must not be treated as a like-for-like speed benchmark.

## Tests and production build

From the project root on macOS / Linux:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
node --test tests/environment.test.mjs tests/playback.test.mjs
npm --prefix frontend run build
```

On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python.exe` and use
`npm.cmd` if needed. The build runs TypeScript checks and writes `frontend/dist/`.
The documented full app launch uses Vite's development proxy; the static build
alone does not start FastAPI or configure an `/api` proxy.

Latest implementation verification: **31 Python tests passed**, **8 frontend
logic/playback tests passed**, and the production build passed. Coverage includes
original Qiskit behavior, geometry, path connectivity and costs, blocked missions,
EW boundary conservatism, edited matrices reaching QAOA, stale revisions, and
playback. One upstream Starlette/httpx test-client deprecation warning was present.
Native browser capture failed during final editor QA, so pointer interactions
were not visually verified; the automated checks above are the verified coverage.

## Original IBM scenario: standalone CLI

For a terminal-only demonstration, install `requirements-ibm.txt` in the virtual
environment and run from the project root:

```sh
.venv/bin/python -m ibm_qiskit.qiskit_demo
```

If the full API requirements are already installed, no additional install is
needed. On Windows, use the virtual-environment Python path shown above.

Optional flags: `--maxiter`, `--shots`, `--seed`, and `--unsafe-penalty`.
The original CLI uses fixed coordinates `(0,0)`, `(0,4)`, `(4,4)`, `(4,0)`, an EW
circle at `(2,2)` with radius `0.6`, Euclidean edge lengths, and a default
10,000-unit unsafe-edge penalty. It validates safety separately. This regression
mode differs from the editor, which strictly excludes EW cells and uses grid paths.

## API reference

Open **http://127.0.0.1:8000/docs** for interactive schemas and requests.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Confirm the local simulator API is running |
| `GET /api/grid?size=40&scenario=demo` | Load a preset grid and environment; `scenario=regression` loads the corner grid |
| `POST /api/mission/validate` | Validate an edited environment and return paths, costs, and exact comparison |
| `POST /api/mission/run` | Recompute that environment's costs and execute QAOA |
| `GET /api/map`, `GET /api/classical`, `POST /api/qaoa/run` | Original fixed-coordinate regression scenario |
| `POST /api/grid/run` | Preset-grid solver; takes matching `size` and `scenario` query parameters |

An editable environment contains `size`, `revision`, exactly four `nodes`,
`obstacles`, `zones` (`center` and `radius`), and `pathfinding: "dijkstra"`.
The run endpoint accepts `{ "environment": ..., "config": ... }`.
Validation returns `feasible`, `status`, `message`, and the revision. Unreachable
connections are identified where applicable, with no fabricated finite distance.
Responses from old revisions are ignored by the UI. Concurrent solver requests
receive HTTP 409; resetting the frontend does not forcibly terminate a calculation
already running in Python.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| API Offline or route preview does not load | Start terminal 1, verify `/api/health`, then refresh the frontend |
| Health works, but `/api/mission/validate` or `/api/grid` returns 404 | An older backend process is running. Stop it with Ctrl+C and restart from this checkout using `--reload` |
| `No module named qiskit` or `fastapi` | Install `requirements-api.txt` with the same `.venv` Python used to start Uvicorn |
| Dependency installation fails on system Python | Use Python 3.13 and recreate `.venv`; do not reuse a virtual environment copied from another computer |
| `npm ci` cannot find a lockfile or package.json | Run the documented command from the project root with `--prefix frontend` |
| Port 8000 is already in use | Stop the old API instance before restarting. The frontend proxy targets port 8000 |
| Port 5173 is in use | Use Vite's printed local URL, or stop the old frontend instance |
| Run Optimization is disabled | Wait for validation; fix blocked/disconnected checkpoints or reset the environment |
| HTTP 409 | Wait for the previous solver request to finish before retrying |
| No feasible QAOA sample | This is a legitimate approximate-solver outcome; try another supported evaluation budget or reset to the demo |
| Search or flight appears paused | Click Resume, adjust speed, or reset the simulation |

## Repository map and further reading

```text
api/main.py                   FastAPI, environment validation and solver endpoints
ibm_qiskit/grid.py            Grid navigation, obstacles, EW exclusion and search records
ibm_qiskit/qiskit_map.py      Original fixed-node map and exact tour enumeration
ibm_qiskit/qiskit_qaoa.py     QuadraticProgram, QUBO/Ising, QAOA, COBYLA and decoding
ibm_qiskit/qiskit_demo.py     Standalone IBM CLI
frontend/src/                React editor, revision state, visualization and analysis
tests/                       Python and frontend logic/playback tests
requirements-api.txt         Full Python dependency entry point
requirements-ibm.txt         Solver-only Python dependencies
```

A short explanation of the workflow and controls is available in
[Q/ROUTE simple guide](output/pdf/q_route_simple_guide.pdf).
Original decorative image provenance and generation prompts are in
[asset notes](frontend/public/images/ASSETS.md). Fonts and images are bundled
locally; mountain imagery is decorative, not a geographic mission map. The landing
route preview is illustrative and is explicitly labeled as not a solver result.
