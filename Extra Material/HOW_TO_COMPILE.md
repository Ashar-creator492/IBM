# Q-Route — Setup and Run Guide

This project is a Python/Streamlit dashboard for the Q-Route threat-aware UAV routing benchmark.

> **Important:** Python projects are not normally "compiled" into an executable. You install the dependencies and run the dashboard with Streamlit.

## 1. Requirements

- Windows 10/11, macOS, or Linux
- Python 3.10 or newer (Python 3.11 is a good choice)
- VS Code (recommended)
- Internet connection for the initial package installation

Check that Python and pip are available:

```bash
python --version
python -m pip --version
```

On some Windows installations, use `py` instead of `python`:

```powershell
py --version
```

## 2. Extract and open the project

1. Extract the project ZIP file into a normal folder, for example `Q-Route`.
2. Open VS Code.
3. Select **File → Open Folder** and choose the extracted `Q-Route` folder.
4. In VS Code, open **Terminal → New Terminal**.

Make sure the terminal is in the folder containing `app.py` and `requirements.txt`.

## 3. Create a virtual environment

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this once in the current terminal, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Windows Command Prompt

```bat
py -m venv .venv
.venv\Scripts\activate.bat
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

When activated, the terminal prompt normally shows `(.venv)`.

## 4. Install the dependencies

Upgrade pip and install the packages listed in `requirements.txt`:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

This installs the libraries used by the project, including NumPy, Pandas, Plotly, Shapely, Dimod, D-Wave samplers, and Streamlit.

If installation fails, check that the virtual environment is activated and that you are running the command from the project folder.

## 5. Run the dashboard

From the same folder as `app.py`, run:

```bash
streamlit run app.py
```

Streamlit should open the dashboard in your default browser. If it does not, open this address manually:

```text
http://localhost:8501
```

To stop the dashboard, focus the terminal and press **Ctrl + C**.

## 6. Use the dashboard

1. Choose **Classical Computing** or **Quantum Computing (Simulated)** in the sidebar.
2. Configure the mission, EW jamming zones, annealer effort, and benchmark sizes.
3. Click **Run live benchmark** to calculate a new run.
4. Use the dashboard tabs to inspect the race chart, solution quality, route map, and method/limitations.
5. Use **Load saved run** if a compatible saved benchmark is available in `benchmark_cache.json`.

The dashboard's simulated annealing results are produced locally. They are **not** runs on a physical D-Wave QPU.

## 7. Run the project tests (optional)

With the virtual environment active, run:

```bash
python test_benchmark.py
python test_quantum_engine.py
```

These scripts run offline checks for the routing, QUBO, benchmark, and solver-control logic. The quantum-engine tests use stand-in modules for hardware/SDK control-flow checks; they do **not** verify a real D-Wave QPU run.

## 8. Optional: connect to real D-Wave hardware

A real QPU or Leap hybrid run requires:

- A D-Wave Leap account with access to the relevant solver
- A valid Leap API token
- The optional D-Wave Ocean system package (`dwave-system`), which is listed in `requirements.txt`

Configure credentials using the official D-Wave Ocean configuration instructions. Do not commit API tokens, credentials, or `.conf` files containing secrets to GitHub.

The dashboard's **Quantum Computing (Simulated)** mode is a local simulation. Selecting that mode does not send a job to D-Wave hardware. The separate `quantum_solver.py` module contains the hardware/simulator backend logic.

## 9. Common problems

### `streamlit` is not recognized

Activate `.venv`, then run:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

### `ModuleNotFoundError`

Make sure the virtual environment is active and install dependencies again:

```bash
python -m pip install -r requirements.txt
```

### Port 8501 is already in use

Run Streamlit on another port:

```bash
python -m streamlit run app.py --server.port 8502
```

Then visit `http://localhost:8502`.

### Dashboard opens but the benchmark is slow

Start with the **Quick (5–15)** race-size preset and lower the annealer reads/sweeps. Larger QUBO problems can take substantially longer on a local CPU.

---

## Quick start

After Python is installed and the project ZIP has been extracted, the usual Windows PowerShell commands are:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Then open `http://localhost:8501` if the browser does not open automatically.
