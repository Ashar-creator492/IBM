import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUpRight,
  Play,
  Crosshair,
  ShieldCheck,
  Cpu,
  ArrowRight,
  RotateCcw,
  LoaderCircle,
  AlertTriangle,
  ChevronDown,
  Network,
  Layers3,
  Route as RouteIcon,
  ShieldAlert,
} from "lucide-react";
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/500.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/700.css";
import "@fontsource/manrope/800.css";
import {
  request,
  type RouteMap,
  type Classical,
  type Result,
  type Config,
} from "./api";
import "./styles.css";
import { useEnvironment, revisionMatches } from "./environment";
import { MissionGrid, type Grid, type GridHandle } from "./MissionGrid";

const pathLabel = (route: number[] | null | undefined) =>
  route ? route.join(" → ") : "No feasible route";
const format = (value: number | null | undefined, digits = 3) =>
  value == null ? "—" : value.toFixed(digits);
function SectionTitle({
  number,
  title,
  note,
}: {
  number: string;
  title: string;
  note: string;
}) {
  return (
    <div className="section-title">
      <div>
        <span className="eyebrow">
          {number} / {note}
        </span>
        <h2>{title}</h2>
      </div>
      <ArrowUpRight size={30} strokeWidth={1} />
    </div>
  );
}

function RouteCanvas({
  map,
  result,
  hero = false,
  runId = 0,
}: {
  map: RouteMap;
  result?: Result | null;
  hero?: boolean;
  runId?: number;
}) {
  const route = result?.best_feasible_route;
  const safe = result?.best_feasible_safe;
  const point = (node: number) => [
    100 + map.nodes[node][0] * 100,
    500 - map.nodes[node][1] * 100,
  ];
  const center = [
    100 + map.threat_center[0] * 100,
    500 - map.threat_center[1] * 100,
  ];
  const points = route?.map((node) => point(node).join(",")).join(" ");
  return (
    <svg
      viewBox="0 0 600 600"
      className={hero ? "route-svg hero-route" : "route-svg"}
      role="img"
      aria-label={
        hero
          ? `Four-node routing preview. ${result ? (route ? pathLabel(route) : "No feasible quantum sample") : "Illustrative scenario, not a quantum result"}`
          : `Route graph. ${route ? pathLabel(route) : "Awaiting a quantum optimization run"}`
      }
    >
      <defs>
        <pattern
          id={hero ? "hero-grid" : "lab-grid"}
          width="25"
          height="25"
          patternUnits="userSpaceOnUse"
        >
          <path
            d="M 25 0 L 0 0 0 25"
            fill="none"
            stroke="var(--blue)"
            strokeOpacity=".2"
            strokeWidth=".6"
          />
        </pattern>
        <radialGradient id={hero ? "hero-light" : "lab-light"}>
          <stop stopColor="var(--sky)" stopOpacity=".6" />
          <stop offset="1" stopColor="var(--sky)" stopOpacity="0" />
        </radialGradient>
        <marker
          id={hero ? "hero-arrow" : "route-arrow"}
          markerWidth="7"
          markerHeight="7"
          refX="6"
          refY="3"
          orient="auto"
        >
          <path
            d="M0,0 L6,3 L0,6"
            fill={safe ? "var(--green)" : "var(--danger)"}
          />
        </marker>
      </defs>
      <rect
        x="0"
        y="0"
        width="600"
        height="600"
        fill={`url(#${hero ? "hero-light" : "lab-light"})`}
      />
      <rect
        x="30"
        y="30"
        width="540"
        height="540"
        fill={`url(#${hero ? "hero-grid" : "lab-grid"})`}
      />
      {[0, 1, 2, 3, 4].map((n) => (
        <g key={n} className="axis">
          <text x={100 + n * 100} y="553" textAnchor="middle">
            {n}.0
          </text>
          <text x="48" y={504 - n * 100}>
            {n}.0
          </text>
        </g>
      ))}
      {map.nodes.flatMap((_, i) =>
        map.nodes.slice(i + 1).map((__, k) => {
          const j = i + k + 1;
          const [x1, y1] = point(i);
          const [x2, y2] = point(j);
          return (
            <line
              key={`${i}-${j}`}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke={map.unsafe_edges[i][j] ? "var(--danger)" : "var(--blue)"}
              strokeWidth="1.4"
              strokeOpacity={map.unsafe_edges[i][j] ? 0.45 : 0.7}
              strokeDasharray={map.unsafe_edges[i][j] ? "5 7" : undefined}
            />
          );
        }),
      )}
      <circle
        cx={center[0]}
        cy={center[1]}
        r={map.threat_radius * 100 + 10}
        fill="none"
        stroke="#F06464"
        strokeOpacity=".18"
        strokeDasharray="2 5"
      />
      <circle
        cx={center[0]}
        cy={center[1]}
        r={map.threat_radius * 100}
        fill="#F06464"
        fillOpacity=".08"
        stroke="#F06464"
        strokeOpacity=".6"
      />
      <path
        d={`M${center[0] - 10},${center[1]} h20 M${center[0]},${center[1] - 10} v20`}
        stroke="#F06464"
        strokeOpacity=".7"
      />
      <text
        x={center[0]}
        y={center[1] + 95}
        textAnchor="middle"
        className="threat-label"
      >
        EW / EXCLUSION ZONE
      </text>
      {hero && !result && (
        <polyline
          points={[0, 1, 2].map((node) => point(node).join(",")).join(" ")}
          fill="none"
          stroke="var(--green)"
          strokeWidth="4"
        >
          <title>Illustrative path only, not a QAOA result</title>
        </polyline>
      )}
      {points && (
        <g key={runId}>
          <polyline
            points={points}
            fill="none"
            stroke={safe ? "var(--green)" : "var(--danger)"}
            strokeWidth="3"
            strokeLinejoin="round"
            className="route-trace"
            pathLength="1"
          />
          {route?.slice(0, -1).map((node, index) => {
            const a = point(node),
              b = point(route[index + 1]);
            return (
              <line
                key={index}
                x1={(a[0] + b[0]) / 2 - (b[0] - a[0]) * 0.04}
                y1={(a[1] + b[1]) / 2 - (b[1] - a[1]) * 0.04}
                x2={(a[0] + b[0]) / 2}
                y2={(a[1] + b[1]) / 2}
                stroke={safe ? "var(--green)" : "var(--danger)"}
                markerEnd={`url(#${hero ? "hero-arrow" : "route-arrow"})`}
              />
            );
          })}
        </g>
      )}
      {map.nodes.map((coordinate, i) => {
        const [x, y] = point(i);
        return (
          <g key={i} tabIndex={0} className="map-node">
            <title>
              {i === 0 ? "Launch depot" : "Target " + i}: (
              {coordinate.join(", ")}).{" "}
              {map.unsafe_edges[i].filter(Boolean).length} threat-affected
              connection.
            </title>
            <circle
              cx={x}
              cy={y}
              r="25"
              fill={i === 0 ? "var(--green-soft)" : "var(--surface)"}
              stroke={i === 0 ? "var(--green)" : "var(--blue)"}
              strokeOpacity={i === 0 ? 0.7 : 0.35}
            />
            <circle
              cx={x}
              cy={y}
              r="32"
              fill="none"
              stroke={i === 0 ? "var(--green)" : "var(--blue)"}
              strokeOpacity=".2"
            />
            <text
              x={x}
              y={y + 6}
              textAnchor="middle"
              fill={i === 0 ? "var(--green-ink)" : "var(--ink)"}
              fontSize="17"
            >
              0{i}
            </text>
            <text
              x={x}
              y={y + (i < 2 ? 48 : -45)}
              textAnchor="middle"
              className="node-label"
            >
              {i === 0
                ? "LAUNCH DEPOT"
                : "TARGET " + String(i).padStart(2, "0")}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
function History({ values }: { values: number[] }) {
  const low = Math.min(...values),
    high = Math.max(...values),
    span = high - low || 1;
  return (
    <svg
      viewBox="0 0 600 180"
      className="history-chart"
      role="img"
      aria-label="Actual QUBO expectation at each COBYLA evaluation"
    >
      <defs>
        <linearGradient id="history-fill" x1="0" y1="0" x2="0" y2="1">
          <stop stopColor="var(--blue)" stopOpacity=".35" />
          <stop offset="1" stopColor="var(--blue)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[30, 90, 150].map((y) => (
        <line
          key={y}
          x1="0"
          y1={y}
          x2="600"
          y2={y}
          stroke="var(--blue)"
          strokeOpacity=".12"
        />
      ))}
      <polyline
        points={values
          .map(
            (v, i) =>
              `${(i / Math.max(1, values.length - 1)) * 590 + 5},${155 - ((v - low) / span) * 135}`,
          )
          .join(" ")}
        fill="none"
        stroke="var(--blue)"
        strokeWidth="2"
      />
      {values.map((v, i) => (
        <circle
          key={i}
          cx={(i / Math.max(1, values.length - 1)) * 590 + 5}
          cy={155 - ((v - low) / span) * 135}
          r="3"
          fill="var(--green-ink)"
        >
          <title>
            Evaluation {i + 1}: {v.toFixed(3)}
          </title>
        </circle>
      ))}
    </svg>
  );
}
function Analysis({ result }: { result: Result | null }) {
  return (
    <section id="analysis" className="section analysis">
      <SectionTitle
        number="03"
        title="Inside the algorithm."
        note="Quantum analysis"
      />
      {!result ? (
        <div className="analysis-empty">
          <Cpu size={32} strokeWidth={1} />
          <h3>Your experiment, under the microscope.</h3>
          <p>
            Run QAOA to inspect real sampling distributions, optimizer
            evaluations, and the generated circuit.
          </p>
        </div>
      ) : (
        <>
          <div className="analysis-grid">
            <article className="analysis-block">
              <span className="eyebrow">01 / SAMPLING YIELD</span>
              <div className="yield-number">
                {((result.feasible_samples / result.shots) * 100).toFixed(2)}
                <small>%</small>
              </div>
              <div className="yield-bar">
                <span
                  style={{
                    width: `${(result.feasible_samples / result.shots) * 100}%`,
                  }}
                />
              </div>
              <div className="flex justify-between text-sm mt-4">
                <span>
                  <i className="dot" /> {result.feasible_samples} feasible
                </span>
                <span className="muted">
                  {result.shots - result.feasible_samples} infeasible
                </span>
              </div>
              <p className="caption">
                Feasibility requires exactly one node per position and one
                position per node. Safety is checked separately.
              </p>
            </article>
            <article className="analysis-block">
              <span className="eyebrow">02 / OPTIMIZATION HISTORY</span>
              <History values={result.history} />
              <div className="flex justify-between text-xs muted">
                <span>Evaluation 01</span>
                <span>QUBO expectation / {result.iterations} evaluations</span>
              </div>
            </article>
          </div>
          <div className="analysis-grid lower">
            <article className="analysis-block">
              <span className="eyebrow">03 / MOST FREQUENT BITSTRINGS</span>
              <div className="samples">
                {result.top_samples.map((sample) => (
                  <div
                    key={sample.bitstring}
                    title={sample.reason ?? "Valid assignment"}
                  >
                    <code>{sample.bitstring}</code>
                    <div className="sample-bar">
                      <span
                        style={{
                          width: `${(sample.count / result.top_samples[0].count) * 100}%`,
                        }}
                      />
                    </div>
                    <span>{sample.count}</span>
                    <span className={sample.feasible ? "green" : "muted"}>
                      {sample.feasible ? "Valid" : "Invalid"}
                    </span>
                  </div>
                ))}
              </div>
            </article>
            <article className="analysis-block circuit-block">
              <span className="eyebrow">04 / ACTUAL BOUND CIRCUIT</span>
              <h3>
                {result.qubits} qubits. {result.parameters.length} parameters.
              </h3>
              <p className="caption">
                {result.layers} QAOA layers · depth {result.circuit_depth}.
                Expand to inspect the complete circuit generated by Qiskit.
              </p>
              <details>
                <summary>
                  Inspect quantum circuit <ChevronDown size={16} />
                </summary>
                <pre className="circuit-text">{result.circuit_text}</pre>
              </details>
              <div className="parameter-list">
                {result.parameters.map((p, i) => (
                  <span key={i}>
                    θ{i + 1} <b>{p.toFixed(4)}</b>
                  </span>
                ))}
              </div>
            </article>
          </div>
        </>
      )}
    </section>
  );
}
function App() {
  const [map, setMap] = useState<RouteMap | null>(null),
    [classical, setClassical] = useState<Classical | null>(null),
    [result, setResult] = useState<Result | null>(null);
  const [connected, setConnected] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [runId, setRunId] = useState(0);
  const [config, setConfig] = useState<Config>({
    shots: 4096,
    maxiter: 40,
    layers: 2,
    seed: 7,
  });
  const [heroMap, setHeroMap] = useState<RouteMap | null>(null);
  const [controlsHost, setControlsHost] = useState<HTMLDivElement | null>(null);
  const running = useRef(false);
  const gridRef = useRef<GridHandle>(null);
  const [grid, setGrid] = useState<Grid | null>(null);
  const runToken = useRef(0);
  const editor = useEnvironment(() => {
    runToken.current++;
    setResult(null);
    setClassical(null);
    setMap(null);
    gridRef.current?.invalidate();
  });
  type Validation = {
    feasible: boolean;
    revision: number;
    status: string;
    message: string;
    grid: Grid | null;
    result?: Result | null;
  };
  const [validation, setValidation] = useState<Validation | null>(null);
  const [validating, setValidating] = useState(false);
  useEffect(() => {
    const env = editor.environment;
    if (!env) return;
    let cancelled = false;
    setValidation(null);
    setValidating(true);
    const timer = setTimeout(() => {
      request<Validation>("mission/validate", env)
        .then((v) => {
          if (cancelled || !revisionMatches(v, env)) return;
          setValidation(v);
          if (v.grid) {
            setGrid(v.grid);
            setMap(v.grid.map);
            setClassical(v.grid.classical);
          }
        })
        .catch((e) => {
          if (!cancelled) setError(e.message);
        })
        .finally(() => {
          if (!cancelled) setValidating(false);
        });
    }, 180);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [editor.environment]);
  const ready =
    !!editor.environment &&
    validation?.revision === editor.environment.revision &&
    validation.feasible &&
    !validating;
  const [active, setActive] = useState("overview");
  useEffect(() => {
    const sections = ["overview", "lab", "results", "analysis", "technology"];
    const update = () => {
      const current =
        sections
          .filter(
            (id) =>
              (document.getElementById(id)?.getBoundingClientRect().top ??
                Infinity) <
              window.innerHeight * 0.4,
          )
          .at(-1) ?? "overview";
      setActive(current === "results" ? "analysis" : current);
    };
    window.addEventListener("scroll", update, { passive: true });
    update();
    return () => window.removeEventListener("scroll", update);
  }, []);
  const load = () => {
    setError("");
    Promise.all([
      request<Grid>("grid"),
      request<RouteMap>("map"),
      request<{ status: string }>("health"),
    ])
      .then(([m, original]) => {
        setHeroMap(original);
        setGrid(m);
        editor.load(m.environment);
        setMap(m.map);
        setClassical(m.classical);
        setConnected(true);
      })
      .catch((e) => {
        setConnected(false);
        setError(e.message);
      });
  };
  useEffect(load, []);
  async function run() {
    if (running.current || !ready || !editor.environment) return;
    running.current = true;
    setBusy(true);
    setError("");
    const token = ++runToken.current;
    setResult(null);
    try {
      const completed = await gridRef.current?.explore();
      if (!completed || token !== runToken.current) return;
      const response = await request<Validation>("mission/run", {
        environment: editor.environment,
        config,
      });
      if (
        token !== runToken.current ||
        !revisionMatches(response, editor.environment)
      )
        return;
      const data = response.result;
      if (!response.feasible) {
        setValidation(response);
        gridRef.current?.fail();
        return;
      }
      if (!data) throw Error("Missing solver response");
      if (token !== runToken.current) return;
      setResult(data);
      setRunId((id) => id + 1);
    } catch (e) {
      if (token !== runToken.current) return;
      gridRef.current?.fail();
      setError(e instanceof Error ? e.message : "Simulation failed");
    } finally {
      setBusy(false);
      running.current = false;
    }
  }
  return (
    <>
      <a href="#lab" className="skip-link">
        Skip to route lab
      </a>
      <header className="nav glass">
        <a href="#overview" className="wordmark" aria-label="Q Route home">
          Q<span>/</span>ROUTE
        </a>
        <nav aria-label="Main navigation">
          <a
            href="#overview"
            aria-current={active === "overview" ? "location" : undefined}
          >
            Mission
          </a>
          <a
            href="#lab"
            aria-current={active === "lab" ? "location" : undefined}
          >
            Route Lab
          </a>
          <a
            href="#analysis"
            aria-current={active === "analysis" ? "location" : undefined}
          >
            Analysis
          </a>
          <a
            href="#technology"
            aria-current={active === "technology" ? "location" : undefined}
          >
            Technology
          </a>
        </nav>
        <div className="nav-status">
          <small>
            <i className={connected ? "dot" : "dot offline"} />
            {connected ? "Local Simulator" : "API Offline"}
          </small>
        </div>
      </header>
      <main>
        <section
          id="overview"
          className="hero"
          aria-labelledby="mission-heading"
        >
          <div className="hero-visual">
            <div className="mountain-scene" aria-hidden="true">
              <img
                src="/images/alpine-mountains.png"
                alt=""
                fetchPriority="high"
              />
            </div>
            <img
              className="hero-drone"
              src="/images/drone.png"
              alt="White quadcopter with a gimbal camera and illuminated propeller guards"
              fetchPriority="high"
            />
          </div>
          <div className="hero-content">
            <span className="mission-kicker">
              <i /> Quantum routing
            </span>
            <h1 id="mission-heading">
              Smarter
              <br />
              Drone Routes
              <br />
              in Contested
              <br />
              <span>Airspace.</span>
            </h1>
            <p className="hero-description">
              Quantum-assisted optimization for
              <br className="desktop-break" /> safe, efficient drone deliveries
              <br className="desktop-break" /> under electronic warfare threats.
            </p>
            <div
              className="hero-metrics"
              aria-label={
                result
                  ? "Latest experiment configuration"
                  : "Default experiment configuration"
              }
            >
              <div className="metric-pill glass">
                <Network />
                <span>
                  <strong>04</strong>
                  <small>Nodes</small>
                </span>
              </div>
              <div className="metric-pill glass">
                <Cpu />
                <span>
                  <strong>16</strong>
                  <small>Qubits</small>
                </span>
              </div>
              <div className="metric-pill glass">
                <Layers3 />
                <span>
                  <strong>QAOA</strong>
                  <small>({result?.layers ?? 2} Layers)</small>
                </span>
              </div>
            </div>
            <a className="hero-cta" href="#lab">
              Explore Route Lab{" "}
              <span>
                <ArrowRight />
              </span>
            </a>
          </div>
          <div className="hero-aside">
            <div className="preview-card glass">
              {heroMap ? (
                <RouteCanvas map={heroMap} hero />
              ) : (
                <div className="preview-loading">Loading route scenario…</div>
              )}
              <span className="preview-caption">
                {"Scenario preview · not a solver result"}
              </span>
            </div>
            <div className="info-pill glass">
              <div>
                <span className="info-icon danger-icon">
                  <ShieldAlert />
                </span>
                <span>
                  <strong>EW Zone</strong>
                  <small>GPS Jamming</small>
                </span>
              </div>
              <div>
                <span className="info-icon route-icon">
                  <RouteIcon />
                </span>
                <span>
                  <strong>Optimized Route</strong>
                  <small>Threat-Aware</small>
                </span>
              </div>
            </div>
          </div>
          <a
            className="action-preview"
            href="#lab"
            aria-label="See it in action: open the live route lab"
          >
            <img
              src="/images/alpine-mountains.png"
              alt="Snow-covered alpine peaks"
            />
            <div>
              <i />
              <h3>See It in Action</h3>
              <p>Run a live quantum routing simulation</p>
            </div>
            <span className="preview-play">
              <Play size={23} />
            </span>
          </a>
        </section>
        <section id="lab" className="section lab">
          <SectionTitle
            number="01"
            title="Route Lab"
            note="Interactive route lab"
          />
          <div className="lab-intro">
            <p>
              Four locations. One exclusion zone.
              <br />
              Let a quantum circuit explore the way through.
            </p>
            <span className="technical-tag">
              <Crosshair size={14} /> CARTESIAN MICRO-GRID / 4 × 4
            </span>
          </div>
          {error && (
            <div className="error-banner" role="alert">
              <AlertTriangle size={18} />
              <span>{error}</span>
              {!connected && (
                <button onClick={load}>
                  Reconnect <RotateCcw size={14} />
                </button>
              )}
            </div>
          )}
          <div className="lab-workspace">
            <div className="map-panel">
              <div className="map-header">
                <span className="eyebrow">LIVE ROUTING ENVIRONMENT</span>
                <span className="map-state">
                  <i className="dot" />
                  {busy
                    ? "SIMULATING"
                    : result
                      ? "EXPERIMENT COMPLETE"
                      : "AWAITING EXPERIMENT"}
                </span>
              </div>
              {grid ? (
                <MissionGrid
                  key={`${grid.scenario}-${grid.size}`}
                  ref={gridRef}
                  controlsHost={controlsHost}
                  environment={editor.environment}
                  onEdit={(e) => editor.commit(e)}
                  locked={busy}
                  canReplay={!!ready}
                  onUndo={editor.undo}
                  onRedo={editor.redo}
                  onEnvironmentReset={editor.reset}
                  missionStatus={
                    validating
                      ? "Validating / searching grid"
                      : validation
                        ? `${validation.status}: ${validation.message}`
                        : "Environment modified"
                  }
                  grid={grid}
                  result={result}
                  onReset={() => {
                    runToken.current++;
                    setResult(null);
                  }}
                />
              ) : (
                <div className="map-loading">
                  {error
                    ? "Start the local API to load the map."
                    : "Loading map from local API…"}
                </div>
              )}
              <div className="map-legend">
                <span>
                  <i className="legend-line" /> Restricted footprint
                </span>
                <span>
                  <i className="legend-line threat" /> Threat intersection
                </span>
                <span>
                  <i className="legend-line safe" /> Selected grid route
                </span>
              </div>
              {result && (
                <div
                  className={
                    "route-readout " +
                    (result.best_feasible_safe ? "safe-readout" : "")
                  }
                >
                  <span className="eyebrow">
                    {result.best_feasible_route
                      ? "DECODED QAOA ROUTE"
                      : "NO FEASIBLE QAOA SAMPLE"}
                  </span>
                  <strong>{pathLabel(result.best_feasible_route)}</strong>
                  <span>
                    {result.best_feasible_route
                      ? result.best_feasible_safe
                        ? "No threat intersections"
                        : "WARNING: Route intersects threat zone"
                      : "Try another configuration. No classical route has been substituted."}
                  </span>
                </div>
              )}
            </div>
            <aside className="solver-panel glass">
              <div className="flex justify-between items-center">
                <span className="eyebrow">EXPERIMENT CONFIGURATION</span>
                <Cpu size={20} className="lavender" />
              </div>
              <h3>
                Quantum <br />
                control room.
              </h3>
              <p className="caption">
                Prepare the circuit. Set the search budget.
                <br />
                Sample the possibilities.
              </p>
              <div ref={setControlsHost} />
              <div className="restore-controls">
                <button disabled={busy} onClick={editor.restoreNodes}>
                  Restore checkpoints
                </button>
                <button disabled={busy} onClick={editor.resetZones}>
                  Reset EW zones
                </button>
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void run();
                }}
              >
                <fieldset disabled={busy}>
                  <label htmlFor="scenario">Mission layout</label>
                  <select
                    id="scenario"
                    value={grid?.scenario ?? "demo"}
                    onChange={async (e) => {
                      try {
                        const g = await request<Grid>(
                          `grid?size=${grid?.size ?? 40}&scenario=${e.target.value}`,
                        );
                        setGrid(g);
                        editor.load(g.environment);
                        setMap(g.map);
                        setClassical(g.classical);
                        setResult(null);
                      } catch (e) {
                        setError(
                          e instanceof Error ? e.message : "Grid unavailable",
                        );
                      }
                    }}
                  >
                    <option value="demo">
                      Corridor mission · interior targets
                    </option>
                    <option value="regression">
                      Original corner grid · regression
                    </option>
                  </select>
                  <label htmlFor="grid-size">Grid resolution</label>
                  <select
                    id="grid-size"
                    value={grid?.size ?? 40}
                    onChange={async (e) => {
                      try {
                        const g = await request<Grid>(
                          `grid?size=${e.target.value}&scenario=${grid?.scenario ?? "demo"}`,
                        );
                        setGrid(g);
                        editor.load(g.environment);
                        setMap(g.map);
                        setClassical(g.classical);
                        setResult(null);
                      } catch (e) {
                        setError(
                          e instanceof Error ? e.message : "Grid unavailable",
                        );
                      }
                    }}
                  >
                    {[24, 40, 64].map((n) => (
                      <option key={n} value={n}>
                        {n} × {n} cells
                      </option>
                    ))}
                  </select>
                  <label htmlFor="shots">
                    Sampling shots <span>01</span>
                  </label>
                  <select
                    id="shots"
                    value={config.shots}
                    onChange={(e) =>
                      setConfig({ ...config, shots: +e.target.value })
                    }
                  >
                    {[128, 512, 1024, 4096, 8192, 16384].map((n) => (
                      <option key={n} value={n}>
                        {n.toLocaleString()} shots
                      </option>
                    ))}
                  </select>
                  <label htmlFor="maxiter">
                    COBYLA max evaluations <span>02</span>
                  </label>
                  <div className="range-value">
                    <input
                      id="maxiter"
                      type="range"
                      min="8"
                      max="80"
                      value={config.maxiter}
                      onChange={(e) =>
                        setConfig({ ...config, maxiter: +e.target.value })
                      }
                    />
                    <output htmlFor="maxiter">{config.maxiter}</output>
                  </div>
                  <label htmlFor="layers">
                    QAOA circuit layers <span>03</span>
                  </label>
                  <select
                    id="layers"
                    value={config.layers}
                    onChange={(e) =>
                      setConfig({ ...config, layers: +e.target.value })
                    }
                  >
                    {[1, 2, 3].map((n) => (
                      <option key={n} value={n}>
                        {String(n).padStart(2, "0")}{" "}
                        {n === 1 ? "layer" : "layers"}
                        {n === 2 ? " · default" : ""}
                      </option>
                    ))}
                  </select>
                  <button
                    className="button primary run-button"
                    disabled={!connected || busy || !ready}
                    type="submit"
                  >
                    {busy ? (
                      <LoaderCircle size={17} className="spin" />
                    ) : (
                      <Play size={15} fill="currentColor" />
                    )}
                    {busy ? "Simulating…" : "Run Optimization"}
                  </button>
                </fieldset>
              </form>
              <p className="execution-note" role="status" aria-live="polite">
                {busy
                  ? "Running classical grid search, then QAOA visit-order optimization. Playback and solver times are separate."
                  : "Local statevector simulator. No cloud connection or quantum hardware required."}
              </p>
              <div className="solver-footer">
                <ShieldCheck size={16} />
                <span>Explicit geometric safety validation</span>
              </div>
            </aside>
          </div>
        </section>
        <section className="section results" id="results">
          <SectionTitle
            number="02"
            title="The flight, in figures."
            note="Experiment results"
          />
          {!result ? (
            <div className="results-placeholder">
              <span>—</span>
              <p>
                No quantum results yet.
                <br />
                Your first experiment starts in the route lab.
              </p>
            </div>
          ) : (
            <>
              <div className="result-headline">
                <div>
                  <span className="eyebrow">BEST FEASIBLE QAOA COST</span>
                  <div className="big-result">
                    {format(result.best_feasible_cost)}
                    <span>units</span>
                  </div>
                  <div
                    className={result.matched_optimum ? "green" : "lavender"}
                  >
                    {result.matched_optimum
                      ? "↗ Matches the exact classical optimum"
                      : result.best_feasible_route
                        ? "Approximate result · optimum not matched"
                        : "No feasible sample found"}
                  </div>
                </div>
                <div className="result-metrics">
                  {[
                    ["QUBITS", result.qubits],
                    ["CIRCUIT DEPTH", result.circuit_depth],
                    ["LAYERS", result.layers],
                    ["SHOTS", result.shots.toLocaleString()],
                    ["FEASIBLE SHOTS", result.feasible_samples],
                    ["EXECUTION", `${result.elapsed_seconds.toFixed(3)} s`],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <span className="eyebrow">{label}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>
              </div>
              <div className="optimizer-note">
                <AlertTriangle size={16} />
                <div>
                  <strong>
                    COBYLA /{" "}
                    {result.success
                      ? "Converged"
                      : "Stopped without convergence"}
                  </strong>
                  <p>
                    {result.message} {result.iterations} objective evaluations.
                  </p>
                </div>
              </div>
              <div className="comparison">
                <article>
                  <span className="eyebrow">QUANTUM / QAOA</span>
                  <h3>{pathLabel(result.best_feasible_route)}</h3>
                  <div className="comparison-data">
                    <span>
                      Cost <b>{format(result.best_feasible_cost)}</b>
                    </span>
                    <span>
                      Threat safety{" "}
                      <b
                        className={result.best_feasible_safe ? "green" : "red"}
                      >
                        {result.best_feasible_safe === null
                          ? "No route"
                          : result.best_feasible_safe
                            ? "Safe"
                            : "Unsafe"}
                      </b>
                    </span>
                    <span>
                      Execution <b>{result.elapsed_seconds.toFixed(3)} s</b>
                    </span>
                  </div>
                  <p>
                    Approximate optimization, followed by sampling and
                    assignment validation.
                  </p>
                </article>
                <article>
                  <span className="eyebrow">CLASSICAL / EXACT</span>
                  <h3>{pathLabel(classical?.route)}</h3>
                  <div className="comparison-data">
                    <span>
                      Cost <b>{format(classical?.cost)}</b>
                    </span>
                    <span>
                      Threat safety{" "}
                      <b className="green">
                        {classical?.safe ? "Safe" : "Unsafe"}
                      </b>
                    </span>
                    <span>
                      Enumeration{" "}
                      <b>
                        {classical
                          ? (classical.elapsed_seconds * 1000).toFixed(3)
                          : "—"}{" "}
                        ms
                      </b>
                    </span>
                  </div>
                  <p>
                    All six depot-first tours enumerated. Timing covers
                    enumeration only; QAOA timing includes circuit setup,
                    optimization and sampling.
                  </p>
                </article>
              </div>
              <p className="science-note">
                Local quantum simulation demonstrates the algorithm, not quantum
                speedup. The most frequent sample{" "}
                <code>{result.sampled_bitstring}</code> is{" "}
                {result.sampled_route ? "feasible" : "infeasible"}
                {result.sampled_reason ? `: ${result.sampled_reason}` : "."}.
              </p>
            </>
          )}
        </section>
        <Analysis result={result} />
        <section id="technology" className="section technology">
          <SectionTitle
            number="04"
            title="From route to quantum state."
            note="Technology"
          />
          <div className="technology-grid">
            <div>
              <h3>
                A small map.
                <br />A rigorous experiment.
              </h3>
              <p>
                Every node gets a position. Every position gets a node. The
                routing problem becomes an energy landscape for a quantum
                circuit to explore.
              </p>
              <div
                className="science-pipeline"
                aria-label="Routing optimization pipeline"
              >
                <span>
                  <Network size={19} /> Map
                </span>
                <ArrowRight size={15} />
                <span>
                  <Layers3 size={19} /> QUBO
                </span>
                <ArrowRight size={15} />
                <span>
                  <Cpu size={19} /> QAOA
                </span>
              </div>
              <p className="hardware-note">
                Runs on your CPU with Qiskit's local quantum simulator. No
                physical quantum processor is used. All six tours provide an
                exact classical check.
              </p>
            </div>
            <div className="disclosures">
              <details>
                <summary>
                  01 / Threat-aware cost matrix <ChevronDown size={16} />
                </summary>
                {map && (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>FROM / TO</th>
                          {map.nodes.map((_, i) => (
                            <th key={i}>0{i}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {map.costs.map((row, i) => (
                          <tr key={i}>
                            <th>0{i}</th>
                            {row.map((cost, j) => (
                              <td
                                key={j}
                                className={map.unsafe_edges[i][j] ? "red" : ""}
                              >
                                {cost.toFixed(2)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p>
                      Safe grid shortest-path distances. EW regions are
                      excluded; the original straight-edge model uses{" "}
                      {map.unsafe_penalty.toLocaleString()} as its unsafe-edge
                      penalty. Grid costs include closing travel back to the
                      depot is included.
                    </p>
                  </div>
                )}
              </details>
              <details>
                <summary>
                  02 / Assignment & constraints <ChevronDown size={16} />
                </summary>
                <p>
                  16 binary variables xᵢ,ₚ encode node i at position p. For each
                  node, Σₚ xᵢ,ₚ = 1. For each position, Σᵢ xᵢ,ₚ = 1. All 8
                  constraints remain in the model. Decoded cycles rotate to
                  begin and end at depot 0.
                </p>
              </details>
              <details>
                <summary>
                  03 / QUBO & Ising Hamiltonian <ChevronDown size={16} />
                </summary>
                <p>
                  Minimize Σₚ Σᵢ≠ⱼ Wᵢⱼ xᵢ,ₚ xⱼ,(ₚ₊₁) mod 4, plus 1,000 times the
                  sum of squared assignment violations. Qiskit converts x = (1 −
                  Z)/2 into an Ising Hamiltonian and constant offset. Constraint
                  feasibility and geometric threat avoidance are independently
                  validated.
                </p>
              </details>
              <details>
                <summary>
                  04 / Two-layer QAOA <ChevronDown size={16} />
                </summary>
                <p>
                  The default circuit alternates cost evolution with an X mixer
                  twice, starting from a uniform superposition. COBYLA tunes the
                  angles using exact StatevectorEstimator expectations.
                  StatevectorSampler then draws the requested shots. More
                  iterations do not guarantee a better sampled route.
                </p>
              </details>
            </div>
          </div>
        </section>
      </main>
      <footer>
        <a href="#overview" className="wordmark">
          Q<span>/</span>ROUTE
        </a>
        <span>IBM QUANTUM LAB / LOCAL SIMULATION</span>
        <a href="#lab">
          Back to the experiment <ArrowRight size={16} />
        </a>
      </footer>
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
