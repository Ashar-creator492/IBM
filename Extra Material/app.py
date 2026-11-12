"""
app.py -- Q-Route race dashboard (Streamlit).

    streamlit run app.py

Shows classical vs annealer scaling on the SAME threat-aware routing problem.
Everything on the chart is tagged measured / simulated / extrapolated / projected
(see benchmark.py).
"""
import json
import os
import time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from grid_view import PLOT_CONFIG, grid_map_2d, grid_map_3d
from map_engine import generate_mission, route_threat_stats
from qubo_builder import build_qubo, route_cost
from classical_solver import solve_classical_route, solve_heuristic_route
from benchmark import (QPUModel, benchmark_one, build_series, cache_meta,
                         human_time, hybrid_min_time_limit_s, rows_from_dicts,
                         rows_to_dicts, run_annealer_sim)

CACHE_FILE = "benchmark_cache.json"
COL = dict(exact="#c0392b", heur="#e08a00", ann="#2c6fbb", qpu="#1e8e5a")
ALL_SIZES = [5, 6, 8, 10, 12, 14, 15, 16, 18, 20, 22, 24, 26, 28, 30, 32, 36, 40, 45, 50]
DEFAULT_SIZES = [5, 8, 10, 12, 15, 18, 20, 22, 24, 28, 32, 40]

st.set_page_config(layout="wide", page_title="Q-Route | Annealing vs Classical Race")
st.title("Q-Route: threat-aware UAV routing")

# ------------------------------------------------------------------ sidebar
sb = st.sidebar

# ---- 0. Computing Mode (The main toggle for the presentation) --------------
sb.header("0 · Computing Mode")
comp_mode = sb.radio(
    "Algorithm Selection", 
    ["Classical Computing", "Quantum Computing (Simulated)"],
    help="Select the computing paradigm to simulate and visualize across the dashboard."
)
sb.divider()

# ---- 1. Mission ------------------------------------------------------------
sb.header("1 · Mission")
DEPOT_PRESETS = {
    "Random (saved run)": None, "Centre": (50.0, 50.0), "Bottom-left": (10.0, 10.0),
    "Bottom-right": (90.0, 10.0), "Top-left": (10.0, 90.0), "Top-right": (90.0, 90.0),
    "Custom...": "custom",
}
depot_choice = sb.selectbox("Depot (start / return point)", list(DEPOT_PRESETS), index=0)
depot = DEPOT_PRESETS[depot_choice]
if depot == "custom":
    _dx, _dy = sb.columns(2)
    depot = (float(_dx.slider("X (km)", 0, 100, 50)), float(_dy.slider("Y (km)", 0, 100, 50)))

n_threats = sb.slider("EW jamming zones", 0, 8, 3)
gamma = sb.slider("Threat penalty γ", 1.0, 50.0, 10.0)

zones = None
if sb.checkbox("Place EW zones by hand", value=False):
    _zdf = sb.data_editor(
        pd.DataFrame({"x_km": [30.0, 60.0, 50.0], "y_km": [40.0, 65.0, 25.0], "radius_km": [12.0, 10.0, 9.0]}),
        num_rows="dynamic", hide_index=True, key="zone_editor")
    zones = [(float(a), float(b), float(c)) for a, b, c in _zdf.dropna()[["x_km", "y_km", "radius_km"]]
             .itertuples(index=False) if c > 0]
    n_threats = len(zones)
    sb.caption(f"{n_threats} manual zone(s) in use.")

# ---- 2. Solver effort ------------------------------------------------------
sb.header("2 · Annealer effort")
EFFORT = {"Quick (8 reads × 150 sweeps)": (8, 150), "Balanced (16 × 300)": (16, 300),
          "Thorough (32 × 1000)": (32, 1000), "Custom...": None}
effort = sb.selectbox("Effort", list(EFFORT), index=1)
if EFFORT[effort] is None:
    reads = int(sb.slider("Reads", 4, 100, 16))
    sweeps = int(sb.slider("Sweeps per read", 50, 2000, 300, step=50))
else:
    reads, sweeps = EFFORT[effort]

# ---- 3. Race sweep ---------------------------------------------------------
sb.header("3 · Race sizes")
SIZE_PRESETS = {"Quick (5-15)": [5, 8, 10, 12, 15], "Standard (5-40)": [5, 8, 10, 12, 15, 18, 20, 22, 24, 28, 32, 40],
                "Full (5-50)": [5, 8, 10, 12, 15, 18, 20, 22, 24, 28, 32, 36, 40, 45, 50], "Custom...": None}
size_choice = sb.selectbox("Problem sizes N", list(SIZE_PRESETS), index=1)
if SIZE_PRESETS[size_choice] is None:
    sizes = sb.multiselect("Pick sizes (nodes incl. depot)", ALL_SIZES, default=DEFAULT_SIZES)
else:
    sizes = SIZE_PRESETS[size_choice]

show_heur = sb.checkbox("Show classical heuristic (NN + 2-opt)", value=True)
show_extrap = sb.checkbox("Extrapolate exact solver past what could be run", value=True)

with sb.expander("Advanced"):
    seed = int(st.number_input("Random seed", value=42, step=1))
    penalty_mult = st.slider("QUBO penalty λ = k × max(W)", 0.5, 20.0, 10.0)
    r_lo, r_hi = st.slider("EW radius range (km)", 2.0, 30.0, (8.0, 15.0), step=0.5)
    radius_range = (float(r_lo), float(r_hi))
    exact_timeout = st.number_input("Exact solver timeout (s)", value=15.0, min_value=1.0, step=5.0)
    max_mem = st.number_input("Exact solver memory cap (GB)", value=1.0, min_value=0.25, step=0.25)
    ann_cap = st.number_input("Max seconds per size", value=30.0, min_value=2.0, step=5.0)

qpu = QPUModel(programming_ms=16.0, readout_us=60.0, num_reads=100, max_clique=150)

run_clicked = sb.button("▶ Run live benchmark", type="primary", width="stretch")
load_clicked = sb.button("Load saved run", width="stretch", disabled=not os.path.exists(CACHE_FILE))

# ------------------------------------------------------------------ state
if "rows" not in st.session_state:
    st.session_state.rows, st.session_state.meta = [], {}

def race_figure(rows, upto=None):
    """Plotly race chart from benchmark rows, filtered by selected computing mode."""
    s = build_series(rows, qpu, extrapolate=show_extrap)
    fig = go.Figure()
    
    if comp_mode == "Classical Computing":
        em, ex = s["exact_measured"], s["exact_extrap"]
        fig.add_trace(go.Scatter(x=em[0], y=em[1], mode="lines+markers", name="Classical EXACT (Held-Karp) - measured",
                                 line=dict(color=COL["exact"], width=3)))
        if ex[0]:
            fig.add_trace(go.Scatter(x=ex[0], y=ex[1], mode="lines", name="Classical exact - extrapolated (not run)",
                                     line=dict(color=COL["exact"], width=2, dash="dash")))
        if show_heur:
            h = s["heuristic"]
            fig.add_trace(go.Scatter(x=h[0], y=h[1], mode="lines+markers", marker=dict(symbol="square"),
                                     name="Classical heuristic (NN + 2-opt) - measured",
                                     line=dict(color=COL["heur"], width=2)))
        
        if s["exact_wall_n"]:
            fig.add_vline(x=s["exact_wall_n"] - 0.5, line_dash="dot", line_color=COL["exact"],
                          annotation_text="exact DP memory/time wall", annotation_position="top")
    
    else:
        em, ex = s["exact_measured"], s["exact_extrap"]
        fig.add_trace(go.Scatter(x=em[0], y=em[1], mode="lines+markers", name="Classical EXACT (Held-Karp) - measured",
                                 line=dict(color=COL["exact"], width=3)))
        if ex[0]:
            fig.add_trace(go.Scatter(x=ex[0], y=ex[1], mode="lines", name="Classical exact - extrapolated (not run)",
                                     line=dict(color=COL["exact"], width=2, dash="dash")))
        if show_heur:
            h = s["heuristic"]
            if h[0]:
                fig.add_trace(go.Scatter(x=h[0], y=h[1], mode="lines+markers", marker=dict(symbol="square"),
                                         name="Classical heuristic (NN + 2-opt) - measured",
                                         line=dict(color=COL["heur"], width=1, dash="dot")))

        a_x, a_y = s["annealer_sim"]
        fig.add_trace(go.Scatter(x=a_x, y=a_y, mode="lines+markers", marker=dict(symbol="triangle-up"),
                                 name="Annealer simulated on CPU - measured (not QPU time)",
                                 line=dict(color=COL["ann"], width=3)))

        q = s["qpu_projected"]
        if q[0]:
            fig.add_trace(go.Scatter(x=q[0], y=q[1], mode="lines+markers", marker=dict(symbol="diamond"),
                                     name="Quantum annealer (QPU) - MODELED access time",
                                     line=dict(color=COL["qpu"], width=2, dash="dash")))
        hy = s["hybrid_min"]
        if hy[0]:
            fig.add_trace(go.Scatter(x=hy[0], y=hy[1], mode="lines", name="Leap hybrid - documented MINIMUM run time",
                                     line=dict(color=COL["qpu"], width=3, dash="dot")))
        
        if rows:
            fig.add_vline(x=s["pure_qpu_max_n"] + 0.5, line_dash="dot", line_color="#888",
                          annotation_text="pure-QPU embedding limit", annotation_position="top")

    fig.update_layout(title=f"Time to solution vs problem size ({comp_mode})", xaxis_title="N = nodes (QUBO bits = N²)",
                      yaxis_title="seconds", yaxis_type="log", height=520, legend=dict(orientation="h", y=-0.25),
                      margin=dict(t=60))
    if upto:
        fig.update_xaxes(range=[min(sizes) - 1, max(sizes) + 1])
    return fig

# ------------------------------------------------------------------ actions
if run_clicked:
    if not sizes:
        st.error("Pick at least one problem size.")
    else:
        sizes_sorted = sorted(sizes)
        bar, status, chart_ph = st.progress(0.0), st.empty(), st.empty()
        rows = []
        for i, n in enumerate(sizes_sorted):
            status.info(f"Solving N = {n} ...")
            rows.append(benchmark_one(n, n_threats=n_threats, gamma=gamma, seed=seed, exact_timeout=exact_timeout,
                                      max_memory_gb=max_mem, anneal_reads=reads, anneal_sweeps=sweeps,
                                      anneal_max_seconds=ann_cap, penalty_mult=penalty_mult, qpu=qpu,
                                      radius_range=radius_range, depot=depot, zones=zones))
            bar.progress((i + 1) / len(sizes_sorted))
            chart_ph.plotly_chart(race_figure(rows, upto=True), width="stretch", key=f"live_{i}", theme=None)
        status.success("Benchmark finished.")
        st.session_state.rows, st.session_state.meta = rows, cache_meta()
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump({"meta": st.session_state.meta, "rows": rows_to_dicts(rows)}, f, indent=1)
        except OSError:
            pass
elif load_clicked:
    with open(CACHE_FILE) as f:
        blob = json.load(f)
    st.session_state.rows = rows_from_dicts(blob["rows"])
    st.session_state.meta = blob.get("meta", {})

rows = st.session_state.rows

tab_race, tab_quality, tab_map, tab_method = st.tabs(["The race", "Solution quality", "Route map", "Method & limits"])

# ------------------------------------------------------------------ race
with tab_race:
    if not rows:
        st.info("Press **Run live benchmark** (about a minute) or **Load saved run** in the sidebar.")
    else:
        if not run_clicked:
            st.plotly_chart(race_figure(rows), width="stretch", key="race_static", theme=None)

        ns = [r.n for r in rows]
        pick = st.select_slider("Scoreboard for N =", options=ns, value=ns[-1])
        r = next(x for x in rows if x.n == pick)
        
        if comp_mode == "Classical Computing":
            c1, c2 = st.columns(2)
            c1.metric("Classical Exact (Held-Karp)", human_time(r.exact_time) if r.exact_time else "could not run",
                      delta=r.exact_status, delta_color="off")
            c2.metric("Classical Heuristic (NN+2-opt)", human_time(r.heur_time), delta=f"{r.gap(r.heur_cost):+.1f}% vs best known",
                      delta_color="off")
        else:
            c0, c1, c2 = st.columns(3)
            if r.exact_time:
                c0.metric("Classical Exact (Held-Karp)", human_time(r.exact_time), delta="measured", delta_color="off")
            else:
                _sx = build_series(rows, qpu, extrapolate=True)["exact_extrap"]
                _ev = dict(zip(*_sx)).get(r.n)
                c0.metric("Classical Exact (Held-Karp)", "could not run",
                          delta=(f"extrapolated ~{human_time(_ev)}" if _ev else r.exact_status), delta_color="off")
            c1.metric("Annealer simulated on CPU (measured)", human_time(r.ann_time) if r.ann_time else "n/a",
                      delta=(f"{r.gap(r.ann_cost):+.1f}% vs best known" if r.ann_cost else "no feasible tour"),
                      delta_color="off", help=f"feasible reads: {r.ann_feasible}")
            if r.pure_qpu_fits:
                c2.metric("Real QPU (modeled, not run)", human_time(r.qpu_proj_time), delta="projection from D-Wave timing", delta_color="off")
            else:
                c2.metric("Quantum hybrid (modeled minimum)", human_time(r.hybrid_min_time), delta="documented minimum run time", delta_color="off")

# ------------------------------------------------------------------ quality
with tab_quality:
    if not rows:
        st.info("Run or load a benchmark first.")
    else:
        gaps = go.Figure()
        if comp_mode == "Classical Computing":
            gaps.add_bar(x=[r.n for r in rows], y=[r.gap(r.heur_cost) for r in rows], name="Heuristic (NN+2-opt)", marker_color=COL["heur"])
        else:
            gaps.add_bar(x=[r.n for r in rows], y=[r.gap(r.ann_cost) for r in rows], name="Quantum Simulation", marker_color=COL["ann"])
            
        gaps.update_layout(barmode="group", title=f"Tour cost above best known (%) - {comp_mode}",
                           xaxis_title="N", yaxis_title="% above best known", height=380)
        st.plotly_chart(gaps, width="stretch", key="gaps", theme=None)

# ------------------------------------------------------------------ map
with tab_map:
    st.markdown(f"**Current Mode:** {comp_mode} | Set your nodes and solve a single instance to map the routes.")
    mc1, mc2 = st.columns([1, 3])
    with mc1:
        n_map = int(st.slider("N (nodes)", 5, 30, 10, key="n_map"))
        bits = n_map * n_map

        view_mode = st.radio("Map style", ["2D grid", "3D grid", "Plain grid"], key="view_mode")
        show_arrows = st.checkbox("Direction arrows", value=True, disabled=view_mode == "3D grid")
        solve_clicked = st.button(f"Solve ({comp_mode})", type="primary")

    cur_sig = (n_map, n_threats, gamma, seed, radius_range, depot, tuple(zones) if zones else None,
               comp_mode, penalty_mult)

    if solve_clicked:
        m = generate_mission(n_map, n_threats, radius_range=radius_range, gamma=gamma, seed=seed,
                             depot=depot, zones=zones)
        routes, notes, sa_name, dw_name = {}, [], None, None
        
        start_time = time.perf_counter()

        if comp_mode == "Classical Computing":
            ex = solve_classical_route(m.W, timeout=exact_timeout, max_memory_gb=max_mem) if n_map <= 22 else None
            he = solve_heuristic_route(m.W)
            if ex is not None and ex.route:
                routes["Exact (Held-Karp)"] = dict(route=ex.route, kind="exact", dash="dash")
            routes["Heuristic (NN+2-opt)"] = dict(route=he.route, kind="heur", dash="dot")
            
            end_time = time.perf_counter()
            exec_time = end_time - start_time
            notes.append(f"**Classical Execution:** Exact & Heuristic algorithms successfully calculated in {exec_time:.4f} seconds.")
            
        else:
            with st.spinner(f"Simulating annealer on {bits} QUBO bits..."):
                ar = run_annealer_sim(m.W, penalty_mult, reads, sweeps, seed + 1, ann_cap)
            
            exec_time = ar.wall_time
            notes.append(f"**Annealer simulated on CPU:** {exec_time:.4f} s measured. A real QPU would take about "
                         f"{qpu.access_seconds():.3f} s (modeled from D-Wave timing, not run).")

            if ar.route:
                sa_name = "Quantum Simulation"
                routes[sa_name] = dict(route=ar.route, kind="sa", dash="solid")

        st.session_state.map_result = dict(sig=cur_sig, m=m, routes=routes, notes=notes, sa=sa_name, dw=dw_name,
                                           seed=seed, id=st.session_state.get("map_runs", 0) + 1, exec_time=exec_time)
        st.session_state.map_runs = st.session_state.map_result["id"]

    res = st.session_state.get("map_result")
    with mc2:
        if res is None:
            st.info("Pick settings on the left and press the Solve button.")
        else:
            if res["sig"] != cur_sig:
                st.info("Settings changed since last solve. Press Solve to refresh.")
            
            st.success(f"Computation Complete: {res.get('exec_time', 0.0):.4f} seconds")

            def draw(title, names, key):
                sel = {k: res["routes"][k] for k in names if k in res["routes"]}
                uirev = f"run{res['id']}"
                if view_mode == "3D grid":
                    fig = grid_map_3d(res["m"], sel, title=title, uirevision=uirev)
                else:
                    fig = grid_map_2d(res["m"], sel, style="plain" if view_mode == "Plain grid" else "grid",
                                      arrows=show_arrows, title=title, uirevision=uirev)
                st.plotly_chart(fig, width="stretch", key=f"{key}_{view_mode}", config=PLOT_CONFIG, theme=None)

            draw(f"Routes mapped using {comp_mode}", list(res["routes"]), "map_all")

            for note in res["notes"]:
                st.markdown("- " + note)
            
            stats = []
            for name, spec in res["routes"].items():
                t = route_threat_stats(spec["route"], res["m"])
                stats.append({"route": name, "weighted cost": round(route_cost(spec["route"], res["m"].W), 1),
                              "km total": round(t["km_total"], 1), "km inside threat": round(t["km_in_threat"], 1),
                              "edges touching threat": t["edges_in_threat"]})
            if stats:
                st.dataframe(pd.DataFrame(stats), hide_index=True, width="stretch")
            elif comp_mode == "Quantum Computing (Simulated)":
                st.error("The quantum simulation returned no feasible tour for this instance.")

# ------------------------------------------------------------------ method
with tab_method:
    st.markdown(f"""
### Methodology ({comp_mode})
This dashboard simulates pathfinding parameters mapped across Classical processing (Exact/Heuristic) and Simulated Quantum (Annealing).
By leveraging the global toggle in the sidebar, you can visualize and directly compare the calculation times, routes, and overall structural efficiency of both paradigms in isolation.
""")