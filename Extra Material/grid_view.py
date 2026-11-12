"""
grid_view.py -- clean grid-style map rendering for the Q-Route dashboard.

Replaces the satellite/terrain look of aerial_view.py with the look of the "control room" grid:
a light cell grid, numbered checkpoints (00 = depot), a soft red EW disc and glowing route lines.

    grid_map_2d(m, routes, style="grid" | "plain", ...)   flat map (cell grid, or minimal black-on-white)
    grid_map_3d(m, routes, ...)                           same grid as a 3D plate: EW zones are
                                                          translucent cylinders, checkpoints are pins

`routes` has the same format as before:
    {name: {"route": [node order], "kind": exact|heur|sa|dwave|fallback, "dash": "solid"|"dash"|"dot"}}

Nothing here feeds the optimiser. Only distances and EW zones do (map_engine.py). Routes are drawn as the
straight segments the solvers actually score, not as grid-snapped paths, so what you see is what was costed.

plotly is imported lazily so the helpers can be imported without it.
"""
import numpy as np

GRID_KM = 100.0

# kind -> colour. Roadmap: green = quantum path, blue = classical path.
PAL = dict(exact="#2563eb", heur="#f59e0b", sa="#7c3aed", dwave="#22c55e", fallback="#64748b")
PAL_PLAIN = dict(exact="#c0392b", heur="#e08a00", sa="#2c6fbb", dwave="#1e8e5a", fallback="#7f8c8d")

PLOT_CONFIG = {"scrollZoom": True, "displaylogo": False, "doubleClick": "reset",
               "modeBarButtonsToRemove": ["select2d", "lasso2d"]}


def _color(kind, plain):
    return (PAL_PLAIN if plain else PAL).get(kind, "#888888")


def _rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _label(i):
    return f"{i:02d}"


# ------------------------------------------------------------------ 2D
def grid_map_2d(m, routes, style="grid", arrows=True, title="", uirevision="map", height=640, cell_km=2.5):
    """Flat map. style='grid' -> soft cell grid + glowing routes; style='plain' -> minimal black on white."""
    import plotly.graph_objects as go

    plain = style == "plain"
    fig = go.Figure()

    zone_line = "#444444" if plain else "#b91c1c"
    zone_fill = "rgba(0,0,0,0.05)" if plain else "rgba(220,38,38,0.10)"
    for c, r in zip(m.threat_centers, m.threat_radii):
        fig.add_shape(type="circle", xref="x", yref="y", layer="below",
                      x0=c[0] - r, y0=c[1] - r, x1=c[0] + r, y1=c[1] + r,
                      fillcolor=zone_fill, line=dict(color=zone_line, width=1.5))
    if len(m.threat_radii):
        fig.add_trace(go.Scatter(
            x=m.threat_centers[:, 0], y=m.threat_centers[:, 1], mode="text", name="EW jamming zone",
            text=[f"EW {k + 1}" for k in range(len(m.threat_radii))], textfont=dict(color=zone_line, size=12),
            hovertext=[f"EW zone {k + 1}: centre ({c[0]:.1f}, {c[1]:.1f}) km, radius {r:.1f} km"
                       for k, (c, r) in enumerate(zip(m.threat_centers, m.threat_radii))],
            hoverinfo="text"))

    arrow_ann = []
    for name, spec in routes.items():
        route, kind = list(spec["route"]), spec.get("kind", "sa")
        color = _color(kind, plain)
        loop = route + [route[0]]
        px, py = m.coords[loop, 0], m.coords[loop, 1]
        if not plain:                                             # soft glow underneath
            fig.add_trace(go.Scatter(x=px, y=py, mode="lines", showlegend=False, hoverinfo="skip",
                                     line=dict(color=_rgba(color, 0.18), width=12)))
        fig.add_trace(go.Scatter(x=px, y=py, mode="lines", name=name, hoverinfo="name",
                                 line=dict(color=color, width=4 if kind in ("dwave", "sa", "fallback") else 3,
                                           dash=spec.get("dash", "solid"))))
        if arrows:
            for a, b in zip(loop[:-1], loop[1:]):
                p, q = m.coords[a], m.coords[b]
                if np.linalg.norm(q - p) < 5.0:
                    continue
                t0, t1 = p + (q - p) * 0.46, p + (q - p) * 0.54
                arrow_ann.append(dict(x=t1[0], y=t1[1], ax=t0[0], ay=t0[1], xref="x", yref="y", axref="x",
                                      ayref="y", text="", showarrow=True, arrowhead=3, arrowsize=1.3,
                                      arrowwidth=2, arrowcolor=color))

    n = m.n
    edge = "#111111" if plain else "#334155"
    fig.add_trace(go.Scatter(
        x=m.coords[1:, 0], y=m.coords[1:, 1], mode="markers+text", name="Checkpoints",
        marker=dict(size=26, color="white", line=dict(color=edge, width=2)),
        text=[_label(i) for i in range(1, n)], textposition="middle center",
        textfont=dict(color="#0f172a", size=11),
        hovertext=[f"Checkpoint {_label(i)}: ({m.coords[i, 0]:.1f}, {m.coords[i, 1]:.1f}) km" for i in range(1, n)],
        hoverinfo="text"))
    fig.add_trace(go.Scatter(
        x=[m.coords[0, 0]], y=[m.coords[0, 1]], mode="markers+text", name="Depot (00)",
        marker=dict(size=30, color="white", line=dict(color="#16a34a" if not plain else "#111111", width=4)),
        text=["00"], textposition="middle center", textfont=dict(color="#0f172a", size=12),
        hovertext=[f"Depot 00: ({m.coords[0, 0]:.1f}, {m.coords[0, 1]:.1f}) km"], hoverinfo="text"))

    # outer border of the 100 x 100 km field
    fig.add_shape(type="rect", xref="x", yref="y", layer="above", x0=0, y0=0, x1=GRID_KM, y1=GRID_KM,
                  fillcolor="rgba(0,0,0,0)", line=dict(color="#94a3b8", width=1.5))

    major = "rgba(100,116,139,0.30)"
    minor = "rgba(148,163,184,0.20)"
    fig.update_layout(
        title=title, height=height, dragmode="pan", uirevision=uirevision,
        margin=dict(l=10, r=10, t=50, b=10), annotations=arrow_ann,
        paper_bgcolor="white", plot_bgcolor="white" if plain else "#f4f7fb",
        legend=dict(orientation="h", y=-0.06, x=0))
    fig.update_xaxes(range=[-1, 101], constrain="domain", scaleanchor="y", scaleratio=1, dtick=10, tick0=0,
                     showgrid=True, gridcolor=major, zeroline=False, title="km east", layer="below traces",
                     minor=dict(dtick=cell_km, tick0=0, showgrid=True, gridcolor=minor))
    fig.update_yaxes(range=[-1, 101], constrain="domain", dtick=10, tick0=0, showgrid=True, gridcolor=major,
                     zeroline=False, title="km north", layer="below traces",
                     minor=dict(dtick=cell_km, tick0=0, showgrid=True, gridcolor=minor))
    return fig


# ------------------------------------------------------------------ 3D
def grid_map_3d(m, routes, title="", uirevision="map3d", height=640, cell_km=5.0, dome_height=14.0,
                fly_alt=3.0):
    """3D grid plate: flat cell grid, EW zones as translucent cylinders, checkpoints as pins."""
    import plotly.graph_objects as go

    fig = go.Figure()
    flat = [[0, "#eef2f7"], [1, "#eef2f7"]]
    fig.add_trace(go.Surface(x=[[0, GRID_KM], [0, GRID_KM]], y=[[0, 0], [GRID_KM, GRID_KM]],
                             z=[[0, 0], [0, 0]], colorscale=flat, showscale=False, hoverinfo="skip",
                             lighting=dict(ambient=1.0, diffuse=0.0, specular=0.0)))

    gx, gy, gz = [], [], []
    for v in np.arange(0.0, GRID_KM + 1e-9, cell_km):
        gx += [v, v, None]
        gy += [0.0, GRID_KM, None]
        gz += [0.05, 0.05, None]
        gx += [0.0, GRID_KM, None]
        gy += [v, v, None]
        gz += [0.05, 0.05, None]
    fig.add_trace(go.Scatter3d(x=gx, y=gy, z=gz, mode="lines", showlegend=False, hoverinfo="skip",
                               line=dict(color="#c3cddb", width=1)))

    red = [[0, "rgb(220,38,38)"], [1, "rgb(220,38,38)"]]
    theta = np.linspace(0, 2 * np.pi, 49)
    for k, (c, r) in enumerate(zip(m.threat_centers, m.threat_radii)):
        ring_x, ring_y = c[0] + r * np.cos(theta), c[1] + r * np.sin(theta)
        # translucent cylinder wall
        fig.add_trace(go.Surface(
            x=np.vstack([ring_x, ring_x]), y=np.vstack([ring_y, ring_y]),
            z=np.vstack([np.zeros_like(theta), np.full_like(theta, dome_height)]),
            colorscale=red, showscale=False, opacity=0.22, name="EW jamming zone", showlegend=(k == 0),
            hovertext=f"EW zone {k + 1}: radius {r:.1f} km", hoverinfo="text"))
        # footprint disc on the ground
        fig.add_trace(go.Surface(
            x=np.vstack([np.full_like(theta, c[0]), ring_x]), y=np.vstack([np.full_like(theta, c[1]), ring_y]),
            z=np.full((2, theta.size), 0.1), colorscale=red, showscale=False, opacity=0.35,
            hoverinfo="skip"))

    for name, spec in routes.items():
        route = list(spec["route"])
        loop = route + [route[0]]
        kind = spec.get("kind", "sa")
        fig.add_trace(go.Scatter3d(
            x=m.coords[loop, 0], y=m.coords[loop, 1], z=np.full(len(loop), fly_alt), mode="lines", name=name,
            line=dict(color=_color(kind, False), width=7, dash=spec.get("dash", "solid"))))

    # pins: a thin stem from the ground to flight altitude, then the numbered marker on top
    sx, sy, sz = [], [], []
    for x, y in m.coords:
        sx += [x, x, None]
        sy += [y, y, None]
        sz += [0.0, fly_alt, None]
    fig.add_trace(go.Scatter3d(x=sx, y=sy, z=sz, mode="lines", showlegend=False, hoverinfo="skip",
                               line=dict(color="#64748b", width=2)))
    fig.add_trace(go.Scatter3d(
        x=m.coords[1:, 0], y=m.coords[1:, 1], z=np.full(m.n - 1, fly_alt), mode="markers+text", name="Checkpoints",
        marker=dict(size=7, color="white", line=dict(color="#334155", width=2)),
        text=[_label(i) for i in range(1, m.n)], textposition="top center",
        textfont=dict(color="#0f172a", size=11),
        hovertext=[f"Checkpoint {_label(i)}: ({m.coords[i, 0]:.1f}, {m.coords[i, 1]:.1f}) km"
                   for i in range(1, m.n)], hoverinfo="text"))
    fig.add_trace(go.Scatter3d(
        x=[m.coords[0, 0]], y=[m.coords[0, 1]], z=[fly_alt], mode="markers+text", name="Depot (00)",
        marker=dict(size=10, color="#16a34a", symbol="diamond", line=dict(color="#0f172a", width=1)),
        text=["00"], textposition="top center", textfont=dict(color="#166534", size=13),
        hovertext=[f"Depot 00: ({m.coords[0, 0]:.1f}, {m.coords[0, 1]:.1f}) km"], hoverinfo="text"))

    axis = dict(range=[0, GRID_KM], showbackground=False, showgrid=False, zeroline=False)
    fig.update_layout(
        title=title, height=height, uirevision=uirevision, margin=dict(l=0, r=0, t=50, b=0),
        paper_bgcolor="white", legend=dict(orientation="h", y=-0.02, x=0),
        scene=dict(xaxis=dict(axis, title="km east"), yaxis=dict(axis, title="km north"),
                   zaxis=dict(visible=False, range=[0, dome_height * 1.4]),
                   aspectmode="manual", aspectratio=dict(x=1, y=1, z=0.3),
                   camera=dict(eye=dict(x=1.3, y=-1.5, z=1.15))))
    return fig
