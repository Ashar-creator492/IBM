"""
aerial_view.py -- aerial-style map rendering for the Q-Route dashboard.

    make_terrain(seed)            synthetic elevation grid, numpy only, deterministic per seed
    route_map_figure(...)         2D aerial (or plain) map: terrain, EW domes, depot, targets, routes
    route_map_3d(...)             3D flyover: terrain surface, EW domes as cylinders, routes draped on terrain

The terrain is DECORATIVE. It does not feed the QUBO or the weight matrix: only distances and EW
zones do. It exists so the 100 x 100 km grid reads as an aerial view in the demo.

Zoom/pan: ranges are fixed with constrain="domain" + a 1:1 aspect, dragmode is "pan", scroll-wheel zoom
is enabled via PLOT_CONFIG, and `uirevision` keeps the user's zoom across Streamlit reruns.

plotly is imported lazily so make_terrain / aerial_field can be used and tested without it.
"""
import numpy as np

GRID_KM = 100.0

# dark satellite-ish palette: water -> forest -> scrub -> dry earth -> rock
AERIAL_SCALE = [
    [0.00, "#14323f"], [0.16, "#1f4a4f"], [0.30, "#2f5d3a"], [0.48, "#4f7a45"],
    [0.64, "#7d8f4e"], [0.78, "#a39a6b"], [0.90, "#8c8577"], [1.00, "#cfcac0"],
]

# kind -> colour.  Roadmap: neon-green = quantum path, blue = classical path.
PAL_AERIAL = dict(exact="#4cc9f0", heur="#ffd23f", sa="#f15bb5", dwave="#39ff14", fallback="#ffffff")
PAL_PLAIN = dict(exact="#c0392b", heur="#e08a00", sa="#2c6fbb", dwave="#1e8e5a", fallback="#7f8c8d")

PLOT_CONFIG = {"scrollZoom": True, "displaylogo": False, "doubleClick": "reset",
               "modeBarButtonsToRemove": ["select2d", "lasso2d"]}


# ------------------------------------------------------------------ terrain
def _upsample(g, res):
    """Smoothstep-bilinear upsample of a coarse random grid g (n x n) to (res x res)."""
    n = g.shape[0]
    u = np.linspace(0, n - 1, res)
    i0 = np.minimum(u.astype(int), n - 2)
    f = u - i0
    f = f * f * (3 - 2 * f)
    rows = g[i0] * (1 - f)[:, None] + g[i0 + 1] * f[:, None]          # (res, n)
    return rows[:, i0] * (1 - f)[None, :] + rows[:, i0 + 1] * f[None, :]


def make_terrain(seed=42, res=110):
    """Elevation in [0, 1], shape (res, res), indexed [y, x]. Same seed -> same terrain."""
    rng = np.random.default_rng(int(seed) + 7919)
    z, amp, total = np.zeros((res, res)), 1.0, 0.0
    for cells in (4, 8, 16, 32):                  # four octaves of value noise
        z += amp * _upsample(rng.random((cells + 1, cells + 1)), res)
        total += amp
        amp *= 0.5
    z /= total
    z = (z - z.min()) / max(float(z.max() - z.min()), 1e-12)
    return z


def aerial_field(terrain, relief=6.0):
    """Elevation blended with hillshade, in [0, 1]; feed to AERIAL_SCALE for a shaded-relief look."""
    res = terrain.shape[0]
    cell = GRID_KM / (res - 1)
    dzdy, dzdx = np.gradient(terrain * relief * 8.0, cell)            # exaggerate slopes for shading
    nx, ny, nz = -dzdx, -dzdy, np.ones_like(terrain)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    light = np.array([-1.0, 1.0, 1.4])
    light /= np.linalg.norm(light)                                    # sun from the north-west
    shade = np.clip((nx * light[0] + ny * light[1] + nz * light[2]) / norm, 0.0, 1.0)
    shade = (shade - shade.min()) / max(float(shade.max() - shade.min()), 1e-12)
    return np.clip(0.65 * terrain + 0.35 * shade, 0.0, 1.0)


def elevation_at(terrain, x, y, relief=6.0):
    """Terrain height (display units) at grid coordinates x, y (km). Vectorised, nearest cell."""
    res = terrain.shape[0]
    ix = np.clip(np.round(np.asarray(x) / GRID_KM * (res - 1)).astype(int), 0, res - 1)
    iy = np.clip(np.round(np.asarray(y) / GRID_KM * (res - 1)).astype(int), 0, res - 1)
    return terrain[iy, ix] * relief


# ------------------------------------------------------------------ 2D map
def _kind_style(kind, aerial):
    return (PAL_AERIAL if aerial else PAL_PLAIN).get(kind, "#888888")


def route_map_figure(m, routes, terrain=None, aerial=True, arrows=True, title="",
                     uirevision="map", height=640):
    """
    m       : map_engine.Mission
    routes  : {name: {"route": [node order], "kind": exact|heur|sa|dwave|fallback, "dash": "solid"|"dash"|"dot"}}
    aerial  : True -> terrain background + bright route colours; False -> plain white grid
    """
    import plotly.graph_objects as go

    aerial = bool(aerial and terrain is not None)
    fig = go.Figure()
    if aerial:
        xs = np.linspace(0, GRID_KM, terrain.shape[0])
        fig.add_trace(go.Heatmap(x=xs, y=xs, z=aerial_field(terrain), colorscale=AERIAL_SCALE, zmin=0, zmax=1,
                                 showscale=False, showlegend=False, hoverinfo="skip", zsmooth="best"))

    # EW jamming domes: three stacked translucent discs fake a radial fade, plus a dashed outline
    red = "255,59,48" if aerial else "220,0,0"
    for c, r in zip(m.threat_centers, m.threat_radii):
        for frac in (1.0, 0.66, 0.33):
            fig.add_shape(type="circle", xref="x", yref="y", layer="above",
                          x0=c[0] - r * frac, y0=c[1] - r * frac, x1=c[0] + r * frac, y1=c[1] + r * frac,
                          fillcolor=f"rgba({red},0.14)", line=dict(width=0))
        fig.add_shape(type="circle", xref="x", yref="y", layer="above",
                      x0=c[0] - r, y0=c[1] - r, x1=c[0] + r, y1=c[1] + r,
                      line=dict(color=f"rgb({red})", width=2, dash="dash"))
    if len(m.threat_radii):
        fig.add_trace(go.Scatter(
            x=m.threat_centers[:, 0], y=m.threat_centers[:, 1], mode="markers+text", name="EW jamming zone",
            marker=dict(symbol="x", size=9, color=f"rgb({red})"),
            text=[f"EW{k + 1}" for k in range(len(m.threat_radii))], textposition="bottom center",
            textfont=dict(color="white" if aerial else "#900000", size=12, family="Arial Black"),
            hovertext=[f"EW zone {k + 1}: centre ({c[0]:.1f}, {c[1]:.1f}) km, radius {r:.1f} km"
                       for k, (c, r) in enumerate(zip(m.threat_centers, m.threat_radii))],
            hoverinfo="text"))

    # routes (dark underlay first so the bright line stays readable on any terrain)
    arrow_ann = []
    for name, spec in routes.items():
        route, kind = list(spec["route"]), spec.get("kind", "sa")
        color = _kind_style(kind, aerial)
        loop = route + [route[0]]
        px, py = m.coords[loop, 0], m.coords[loop, 1]
        if aerial:
            fig.add_trace(go.Scatter(x=px, y=py, mode="lines", showlegend=False, hoverinfo="skip",
                                     line=dict(color="rgba(0,0,0,0.5)", width=8)))
        fig.add_trace(go.Scatter(x=px, y=py, mode="lines", name=name, hoverinfo="name",
                                 line=dict(color=color, width=4 if kind in ("dwave", "sa", "fallback") else 3,
                                           dash=spec.get("dash", "solid"))))
        if arrows:
            for a, b in zip(loop[:-1], loop[1:]):
                p, q = m.coords[a], m.coords[b]
                if np.linalg.norm(q - p) < 5.0:
                    continue
                t0, t1 = p + (q - p) * 0.45, p + (q - p) * 0.55
                arrow_ann.append(dict(x=t1[0], y=t1[1], ax=t0[0], ay=t0[1], xref="x", yref="y", axref="x",
                                      ayref="y", text="", showarrow=True, arrowhead=3, arrowsize=1.3,
                                      arrowwidth=2, arrowcolor=color))

    # targets + depot
    n = m.n
    fig.add_trace(go.Scatter(
        x=m.coords[1:, 0], y=m.coords[1:, 1], mode="markers+text", name="Targets",
        marker=dict(size=20, color="rgba(15,15,15,0.85)", line=dict(color="white", width=1.5)),
        text=[str(i) for i in range(1, n)], textposition="middle center", textfont=dict(color="white", size=10),
        hovertext=[f"Target {i}: ({m.coords[i, 0]:.1f}, {m.coords[i, 1]:.1f}) km" for i in range(1, n)],
        hoverinfo="text"))
    fig.add_trace(go.Scatter(
        x=[m.coords[0, 0]], y=[m.coords[0, 1]], mode="markers+text", name="Depot (launch)",
        marker=dict(symbol="star", size=28, color="#ffd23f", line=dict(color="#222", width=2)),
        text=["DEPOT"], textposition="top center", 
        textfont=dict(color="white" if aerial else "#222", size=13, family="Arial Black"),
        hovertext=[f"Depot: ({m.coords[0, 0]:.1f}, {m.coords[0, 1]:.1f}) km"], hoverinfo="text"))

    grid = "rgba(255,255,255,0.15)" if aerial else "rgba(0,0,0,0.12)"
    font_c = "#e8e8e8" if aerial else "#222"  # Light gray for aerial, dark grey for plain
    compass = dict(x=0.015, y=0.985, xref="paper", yref="paper", text="N<br>▲", showarrow=False,
                   font=dict(color=font_c, size=13))
                   
    fig.update_layout(
        title=title, height=height, dragmode="pan", uirevision=uirevision,
        margin=dict(l=10, r=10, t=50, b=10), annotations=arrow_ann + [compass],
        plot_bgcolor="#0e1a14" if aerial else "white",
        paper_bgcolor="#0e1a14" if aerial else "white",  # Forces outer background to match
        font=dict(color=font_c),                         # Forces legend and title text to contrast
        legend=dict(orientation="h", y=-0.06, x=0))
    fig.update_xaxes(range=[-2, 102], constrain="domain", scaleanchor="y", scaleratio=1, dtick=10,
                     showgrid=True, gridcolor=grid, zeroline=False, title="km east")
    fig.update_yaxes(range=[-2, 102], constrain="domain", dtick=10, showgrid=True, gridcolor=grid,
                     zeroline=False, title="km north")
    return fig


# ------------------------------------------------------------------ 3D flyover
def route_map_3d(m, routes, terrain, title="", relief=6.0, fly_alt=2.5, dome_height=12.0,
                 uirevision="map3d", height=640):
    """3D aerial flyover. Same `routes` format as route_map_figure."""
    import plotly.graph_objects as go

    res = terrain.shape[0]
    xs = np.linspace(0, GRID_KM, res)
    fig = go.Figure()
    fig.add_trace(go.Surface(x=xs, y=xs, z=terrain * relief, surfacecolor=aerial_field(terrain, relief),
                             colorscale=AERIAL_SCALE, cmin=0, cmax=1, showscale=False, hoverinfo="skip",
                             lighting=dict(ambient=0.8, diffuse=0.6, specular=0.05)))

    theta = np.linspace(0, 2 * np.pi, 49)
    for k, (c, r) in enumerate(zip(m.threat_centers, m.threat_radii)):
        base = float(elevation_at(terrain, c[0], c[1], relief))
        X = np.tile(c[0] + r * np.cos(theta), (2, 1))
        Y = np.tile(c[1] + r * np.sin(theta), (2, 1))
        Z = np.vstack([np.full_like(theta, base), np.full_like(theta, base + dome_height)])
        fig.add_trace(go.Surface(x=X, y=Y, z=Z, opacity=0.28, showscale=False, showlegend=(k == 0),
                                 name="EW jamming zone", colorscale=[[0, "rgb(255,59,48)"], [1, "rgb(255,59,48)"]],
                                 hovertext=f"EW zone {k + 1}: radius {r:.1f} km", hoverinfo="text"))

    for name, spec in routes.items():
        route = list(spec["route"])
        loop = route + [route[0]]
        px, py = [], []
        for a, b in zip(loop[:-1], loop[1:]):                         # sample each leg so it drapes the terrain
            t = np.linspace(0, 1, 30, endpoint=False)
            px.extend(m.coords[a, 0] + (m.coords[b, 0] - m.coords[a, 0]) * t)
            py.extend(m.coords[a, 1] + (m.coords[b, 1] - m.coords[a, 1]) * t)
        px.append(m.coords[loop[-1], 0])
        py.append(m.coords[loop[-1], 1])
        px, py = np.array(px), np.array(py)
        fig.add_trace(go.Scatter3d(x=px, y=py, z=elevation_at(terrain, px, py, relief) + fly_alt, mode="lines",
                                   name=name, line=dict(color=_kind_style(spec.get("kind", "sa"), True), width=6,
                                                        dash=spec.get("dash", "solid"))))

    nz = elevation_at(terrain, m.coords[:, 0], m.coords[:, 1], relief) + fly_alt
    
    # 3D Targets (Updated for contrast and size)
    fig.add_trace(go.Scatter3d(
        x=m.coords[1:, 0], y=m.coords[1:, 1], z=nz[1:], mode="markers+text", name="Targets",
        marker=dict(size=14, color="rgba(15,15,15,0.9)", line=dict(color="white", width=1.5)),
        text=[str(i) for i in range(1, m.n)], 
        textposition="middle center", 
        textfont=dict(color="white", size=11, family="Arial Black")))
    
    # 3D Depot (Updated for contrast and size)
    fig.add_trace(go.Scatter3d(
        x=[m.coords[0, 0]], y=[m.coords[0, 1]], z=[nz[0]], mode="markers+text", name="Depot (launch)",
        marker=dict(size=14, color="#ffd23f", symbol="diamond", line=dict(color="black", width=2)),
        text=["DEPOT"], 
        textposition="top center", 
        textfont=dict(color="black", size=14, family="Arial Black")))

    fig.update_layout(
        title=title, height=height, uirevision=uirevision, margin=dict(l=0, r=0, t=50, b=0),
        legend=dict(orientation="h", y=-0.02, x=0),
        scene=dict(xaxis=dict(range=[0, GRID_KM], title="km east"), yaxis=dict(range=[0, GRID_KM], title="km north"),
                   zaxis=dict(visible=False), aspectmode="manual", aspectratio=dict(x=1, y=1, z=0.3),
                   camera=dict(eye=dict(x=1.35, y=-1.55, z=1.05))))
    return fig