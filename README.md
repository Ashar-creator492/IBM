# Q/ROUTE - IBM Qiskit Mission Lab

An interactive, local demonstration of quantum-assisted drone route planning.
Move delivery checkpoints, draw restricted airspace, and configure electronic
warfare (EW) zones. The application computes safe grid paths, uses QAOA to choose
a visiting order, and compares the sampled result with an exact classical answer.

**Default IBM track:** one drone, one depot, three delivery checkpoints, 16 binary
variables, and 16 simulated qubits. A separate optional six-location experiment
uses a fixed depot, five targets, and 25 assignment qubits. No IBM account, API key, paid service, or
physical quantum processor is required. D-Wave is not part of this implementation.

## Detailed project report

Read the [detailed project report PDF](output/pdf/Q_ROUTE_Detailed_Project_Report.pdf)
or its [Markdown version](docs/PROJECT_REPORT.md) for the architecture,
QAOA mathematics, UI and editor features, classical pathfinding, verified CPU/T4
results, testing, and implementation limitations.

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
`npm ci`. No separate Aer, IBM Runtime, or cloud service setup is needed for the default
four-location mode. The optional 25-qubit experiment uses Aer as described below.

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

Latest implementation verification: **39 Python tests passed**, **9 frontend
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


## Experimental six-location mode: 25 qubits

The four-location mode and its original circuit remain available and unchanged.
Select **Experimental - 6 locations / 25 qubits** in Route Lab to load one depot
and five editable targets. Fifteen Dijkstra paths supply the cost matrix; exact
verification enumerates **120** depot-first tours. The visiting order always
starts and ends at depot 0. This remains a single-drone IBM experiment.

The new encoding fixes the depot outside the assignment matrix. Five targets
assigned to five tour positions require **25 binary variables / qubits**, rather
than the 36 required by the original full six-by-six encoding. Ten one-hot
constraints remain. Departure from the depot and return to it are linear terms;
travel between consecutive target positions is quadratic. Both quantum and exact
classical solvers use the same edited-grid distances.

To reduce invalid assignments, the experimental circuit begins with independent
one-excitation W states for each target row and uses an XY mixer preserving that
row's excitation count. It does **not** start from a classically optimal tour.
Column uniqueness remains an energy constraint and is validated after sampling;
feasibility and optimality are not guaranteed. This mixer and initialization apply
only to the experimental fixed-depot circuit; the original X-mixer circuit is
unchanged. QAOA layers still have two adjustable angles each.

### Local CPU experiment

Install the optional Aer package in the existing environment:

```sh
.venv/bin/python -m pip install -r requirements-aer.txt
```

Restart the API and refresh the frontend. In the experimental mode choose
**Aer CPU - explicit local experiment**. The default experimental preset is
**8 COBYLA evaluations, 1 layer, 4,096 shots**. A 25-qubit double-precision state
alone needs **512 MiB**; execution uses additional buffers and can take substantially
longer than the 16-qubit demo. Do not interpret animation duration as solver time.

The terminal equivalent is:

```sh
.venv/bin/python -m ibm_qiskit.qiskit_experimental --device CPU --maxiter 8 --layers 1 --shots 4096 --output output/six_cpu_result.json
```

To construct and inspect the actual 25-qubit circuit without running it:

```sh
.venv/bin/python -m ibm_qiskit.qiskit_experimental --model-only
```

### NVIDIA GPU / Google Colab experiment

GPU execution requires a compatible NVIDIA GPU and CUDA 12 on x86_64 Linux.
Apple Silicon's GPU is not an NVIDIA CUDA device. The GPU package is optional;
selecting GPU on an unsupported installation reports an error, with **no silent
CPU fallback**. See the upstream [Aer GPU installation instructions](https://github.com/Qiskit/qiskit-aer#installing-gpu-support).

For a suitable Linux environment, install `requirements-gpu.txt` in a fresh virtual
environment instead of `requirements-aer.txt`. Do not install `qiskit-aer` and
`qiskit-aer-gpu` together. The GPU CLI command uses `--device GPU`.

For Colab:

1. Download/open [Q_Route_25_Qubit_GPU.ipynb](notebooks/Q_Route_25_Qubit_GPU.ipynb)
   using Colab's **Upload notebook** action.
2. Select a GPU under **Runtime > Change runtime type**. Free GPU allocation is
   subject to availability; this project does not guarantee access or runtime.
3. Run the upload cell and select the supplied
   [q_route_gpu_source.zip](output/colab/q_route_gpu_source.zip).
4. Run the installation, device check, and execution cells in order. The notebook
   installs the pinned GPU dependencies, runs the real Qiskit Aer primitives,
   reports actual measurements and times, and lets you download the result JSON.

The source ZIP bundles the current Python implementation, so the notebook does
not depend on a GitHub branch having already been pushed. Rebuild it after Python
source changes with `python3 scripts/package_colab.py`. This is a standalone
notebook experiment; it does not automatically connect the Mac's frontend to a
remote Colab server. The local editor can use an explicitly selected Aer CPU, or
an API running on a compatible GPU host with the documented local frontend proxy.

`GET /api/simulator` reports the installed Aer devices. Editable mission endpoints
accept exactly four or six locations. `POST /api/mission/run` accepts an additional
`device: "GPU"` or `device: "CPU"` for six-location execution; device defaults to
GPU for that mode and is ignored by the unchanged four-location solver. Results
include `node_count`, `formulation`, `mixer`, and `simulator_device` metadata.

GPU execution was subsequently verified on a Google Colab T4: 25 qubits, 8
evaluations, 1 layer, 4,096 shots, and 13.297 seconds of solver time. It returned
142 feasible shots and a safe route costing 19.878788, matching the exact optimum.
COBYLA stopped at its evaluation limit without convergence. See the
[actual GPU result](output/experiments/six_gpu_result.json) and
[run notes](output/experiments/six_gpu_run_notes.md). This excludes installation
and runtime allocation time; no quantum speedup is claimed. NVIDIA GPU execution
is not available on this Mac; model and CPU checks run locally.


Verified experimental CPU run (Aer 0.18.2, 8 evaluations, 1 layer, 4,096 shots,
seed 7): **25 qubits**, circuit depth **63**, **142 feasible shots**, route
`0 -> 4 -> 2 -> 5 -> 3 -> 1 -> 0`, cost **19.878788**, matching the exact optimum.
Measured solver runtime was **124.898 seconds** on this local CPU; it is not a
GPU benchmark or runtime promise. COBYLA reached its evaluation limit without
convergence. The [actual result record](output/experiments/six_cpu_result.json)
contains the samples, parameters, history, circuit, and comparison. The earlier
uniform/X-mixer baseline found zero feasible samples; it was not labeled success.
