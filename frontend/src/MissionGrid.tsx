import {
  forwardRef,
  useEffect,
  useMemo,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import type { Result, RouteMap, Classical } from "./api";
import { createPortal } from "react-dom";
import type { Environment } from "./environment";
import { useGridEditor } from "./useGridEditor";
import { PlaybackClock, searchFrame, stitchRoute } from "./playback";
export type Cell = [number, number];
export type Grid = {
  environment: Environment;
  zones: Environment["zones"];
  scenario: string;
  size: number;
  step: number;
  nodes: Cell[];
  obstacles: Cell[];
  danger: Cell[];
  threat_center: Cell;
  threat_radius: number;
  search_seconds: number;
  pairs: {
    source: number;
    target: number;
    path: Cell[];
    explored: Cell[];
    frontier_steps: Cell[][];
    cost: number;
  }[];
  map: RouteMap;
  classical: Classical;
};
export type GridHandle = {
  explore: () => Promise<boolean>;
  invalidate: () => void;
  fail: () => void;
};
export const MissionGrid = forwardRef<
  GridHandle,
  {
    grid: Grid;
    result: Result | null;
    onReset: () => void;
    environment?: Environment | null;
    onEdit?: (e: Environment) => void;
    locked?: boolean;
    canReplay?: boolean;
    missionStatus?: string;
    onUndo?: () => void;
    onRedo?: () => void;
    onEnvironmentReset?: () => void;
    controlsHost: HTMLDivElement | null;
  }
>(function MissionGrid(
  {
    grid,
    result,
    onReset,
    controlsHost,
    environment = null,
    onEdit,
    locked = false,
    canReplay = false,
    missionStatus,
    onUndo = () => {},
    onRedo = () => {},
    onEnvironmentReset = () => {},
  },
  ref,
) {
  const [stage, setStage] = useState("Environment ready"),
    [progress, setProgress] = useState(0),
    [paused, setPaused] = useState(false),
    [speed, setSpeed] = useState(1),
    [showGrid, setShowGrid] = useState(true),
    [showSearch, setShowSearch] = useState(true),
    [zoom, setZoom] = useState(1),
    [pan, setPan] = useState<Cell>([0, 0]);
  const editor = useGridEditor(
    environment,
    onEdit,
    locked,
    onEnvironmentReset,
    onUndo,
    onRedo,
  );
  const view = environment ?? grid;
  const blockedCount = useMemo(() => {
    const cells = new Set(view.obstacles.map((c) => c.join(",")));
    for (let x = 0; x < view.size; x++)
      for (let y = 0; y < view.size; y++)
        if (
          view.zones.some(
            (z) =>
              Math.max(Math.abs(x - z.center[0]) - 0.5, 0) ** 2 +
                Math.max(Math.abs(y - z.center[1]) - 0.5, 0) ** 2 <=
              z.radius ** 2,
          )
        )
          cells.add(`${x},${y}`);
    return cells.size;
  }, [view]);
  const playback = useRef(new PlaybackClock());
  const drag = useRef<Cell | null>(null);
  const events = grid.pairs.flatMap((p) => p.explored);
  const route = result?.best_feasible_route;
  const { path, stops } = stitchRoute(route, grid.pairs);
  const timer = useRef<number>(0);
  const animate = (total: number, label: string) =>
    new Promise<boolean>((resolve) => {
      const epoch = playback.current.begin(
        total,
        label !== "Drone route playback" ? 1.1 : 0.045,
        label === "Drone route playback" ? [...stops] : [],
      );
      playback.current.paused = false;
      setPaused(false);
      setProgress(0);
      setStage(label);
      let current = 0,
        last = performance.now();
      const tick = (now: number) => {
        if (epoch !== playback.current.epoch) {
          resolve(false);
          return;
        }
        const dt = Math.min(now - last, 80);
        last = now;
        current = playback.current.tick(dt);
        setProgress(current);
        if (current >= total) {
          setStage(
            label === "Classical Dijkstra exploration"
              ? "QAOA · optimizing visit order"
              : label === "Search replay" && !route
                ? "Environment ready"
                : "Mission complete",
          );
          resolve(true);
        } else timer.current = requestAnimationFrame(tick);
      };
      timer.current = requestAnimationFrame(tick);
    });
  useImperativeHandle(ref, () => ({
    explore: () => animate(events.length, "Classical Dijkstra exploration"),
    invalidate: () => {
      playback.current.epoch++;
      setStage("Environment modified");
      setProgress(0);
    },
    fail: () => {
      playback.current.epoch++;
      setStage("Experiment failed · reset or retry");
    },
  }));
  useEffect(() => {
    if (result) {
      if (route && path.length)
        void animate(path.length - 1, "Drone route playback");
      else setStage("No feasible QAOA sample found");
    }
  }, [result]);
  useEffect(
    () => () => {
      playback.current.epoch++;
      cancelAnimationFrame(timer.current);
    },
    [],
  );
  const exploring =
    stage === "Classical Dijkstra exploration" || stage === "Search replay";
  const frame = searchFrame(grid.pairs, progress);
  const revealed =
    stage === "Drone route playback" || stage === "Mission complete";
  const visible = exploring ? frame.explored : [];
  const completedLegs = revealed
    ? [...stops].filter((s) => s <= progress).length
    : 0;
  const destination = route?.[Math.min(completedLegs + 1, view.nodes.length)];
  const visited = new Set(route?.slice(0, completedLegs + 1) ?? []);
  const cellPath = (cells: Cell[]) =>
    cells.map(([x, y]) => `M${x} ${y}h1v1h-1z`).join("");
  const line = (cells: Cell[]) =>
    cells.map(([x, y]) => `${x + 0.5},${y + 0.5}`).join(" ");
  const index = Math.min(path.length - 1, Math.floor(progress));
  const cell = path[index],
    next = path[Math.min(path.length - 1, index + 1)];
  const fraction = progress - Math.floor(progress);
  const drone =
    cell && next
      ? [
          cell[0] + (next[0] - cell[0]) * fraction,
          cell[1] + (next[1] - cell[1]) * fraction,
        ]
      : null;
  const angle =
    cell && next
      ? (Math.atan2(next[1] - cell[1], next[0] - cell[0]) * 180) / Math.PI + 90
      : 0;
  const pointerCell = (e: React.PointerEvent<SVGSVGElement>): Cell => {
    const p = new DOMPoint(e.clientX, e.clientY);
    const matrix = e.currentTarget
      .querySelector<SVGGElement>("g[data-airspace]")
      ?.getScreenCTM();
    const local = matrix ? p.matrixTransform(matrix.inverse()) : p;
    return [
      Math.max(0, Math.min(grid.size - 1, Math.floor(local.x))),
      Math.max(0, Math.min(grid.size - 1, Math.floor(local.y))),
    ];
  };
  return (
    <>
      {editor.controls}
      {missionStatus?.startsWith("No feasible route") && (
        <div className="mission-connectivity-error" role="alert">
          <strong>NO FEASIBLE ROUTE</strong>
          <p>{missionStatus}</p>
          <button type="button" onClick={onEnvironmentReset}>
            Reset Environment
          </button>
          <button type="button" onClick={() => editor.selectTool("draw")}>
            Edit Obstacles
          </button>
        </div>
      )}
      <p className="mission-status" role="status">
        {missionStatus} · {view.nodes.length} checkpoints · {blockedCount}{" "}
        blocked cells ({view.obstacles.length} obstacle cells) ·{" "}
        {view.zones.length} EW zones
        {environment ? ` · Revision ${environment.revision}` : ""}
      </p>
      <div className="mission-toolbar">
        <span role="status">{stage}</span>
        <div>
          <button
            aria-label="Zoom out"
            onClick={() => setZoom((z) => Math.max(1, z - 0.25))}
          >
            −
          </button>
          <output>{Math.round(zoom * 100)}%</output>
          <button
            aria-label="Zoom in"
            onClick={() => setZoom((z) => Math.min(3, z + 0.25))}
          >
            +
          </button>
          <button
            onClick={() => {
              setZoom(1);
              setPan([0, 0]);
            }}
          >
            Fit
          </button>
        </div>
      </div>
      {revealed && (
        <p className="mission-status">
          {stage === "Mission complete"
            ? "Simulated flight complete · returned to depot"
            : `Destination 0${destination} · ${Math.min(view.nodes.length - 1, completedLegs)} / ${view.nodes.length - 1} deliveries · ${Math.round((progress / Math.max(1, path.length - 1)) * 100)}% flight progress`}
        </p>
      )}
      <svg
        className="mission-grid"
        viewBox={`-2 -2 ${grid.size + 4} ${grid.size + 4}`}
        role="img"
        aria-label="Interactive airspace grid. Dijkstra finds safe paths; QAOA chooses target order."
        onPointerDown={(e) => {
          if (locked) return;
          e.currentTarget.setPointerCapture(e.pointerId);
          if (editor.down(pointerCell(e))) return;
          drag.current = [e.clientX, e.clientY];
        }}
        onPointerUp={(e) => {
          editor.up(pointerCell(e));
          drag.current = null;
        }}
        onPointerCancel={() => {
          editor.cancel();
          drag.current = null;
        }}
        onPointerMove={(e) => {
          if (locked) return;
          if (editor.dragging()) {
            editor.move(pointerCell(e));
            return;
          }
          if (drag.current) {
            const bounds = e.currentTarget.getBoundingClientRect();
            setPan((p) => [
              p[0] +
                ((e.clientX - drag.current![0]) * grid.size) / bounds.width,
              p[1] +
                ((e.clientY - drag.current![1]) * grid.size) / bounds.height,
            ]);
            drag.current = [e.clientX, e.clientY];
          }
        }}
      >
        <defs>
          <pattern
            id="mission-cells"
            width="1"
            height="1"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M1 0H0V1"
              fill="none"
              stroke="var(--blue)"
              strokeWidth=".035"
            />
          </pattern>
        </defs>
        <g
          data-airspace="true"
          transform={`translate(${pan[0]} ${pan[1]}) translate(${grid.size / 2} ${grid.size / 2}) scale(${zoom}) translate(${-grid.size / 2} ${-grid.size / 2})`}
        >
          <rect width={grid.size} height={grid.size} rx=".5" fill="#f0f6fa" />
          {showGrid && (
            <rect
              width={grid.size}
              height={grid.size}
              fill="url(#mission-cells)"
            />
          )}
          <path
            d={cellPath(view.obstacles)}
            fill="#9aafbd"
            stroke="#eff5f9"
            strokeWidth=".06"
          />
          {showSearch && (
            <path
              d={cellPath(visible)}
              fill="#9fc9e6"
              opacity={revealed ? 0 : 0.42}
              style={{ transition: "opacity .8s" }}
            />
          )}
          {showSearch && exploring && (
            <path d={cellPath(frame.frontier)} fill="#c3ae74" opacity=".65" />
          )}
          {view.zones.map((z, i) => (
            <g key={i}>
              <circle
                cx={z.center[0] + 0.5}
                cy={z.center[1] + 0.5}
                r={z.radius}
                fill="#ee6b7026"
                stroke={editor.selectedZone === i ? "#bb434d" : "var(--danger)"}
                strokeWidth=".09"
              />
              <text
                x={z.center[0] + 0.5}
                y={z.center[1] + 0.8}
                textAnchor="middle"
                fill="#b4414d"
                fontSize=".8"
              >
                EW {i + 1}
              </text>
            </g>
          ))}
          {exploring &&
            grid.pairs.map((pair, i) => {
              const offset = grid.pairs
                .slice(0, i + 1)
                .reduce((s, p) => s + p.explored.length, 0);
              return progress >= offset ? (
                <polyline
                  key={i}
                  points={line(pair.path)}
                  fill="none"
                  stroke="#548f9d"
                  strokeWidth=".12"
                />
              ) : null;
            })}
          {revealed && (
            <path d={cellPath(path)} fill="var(--green)" opacity=".15" />
          )}
          {revealed && (
            <polyline
              points={line(path)}
              fill="none"
              stroke="var(--green)"
              strokeWidth=".32"
              strokeLinejoin="round"
            />
          )}
          {view.nodes.map(([x, y], i) => (
            <g key={i}>
              <circle
                cx={x + 0.5}
                cy={y + 0.5}
                r=".85"
                fill={
                  i === 0 || (revealed && visited.has(i)) ? "#edffde" : "white"
                }
                stroke={editor.selected === i ? "var(--green-ink)" : "#5f7989"}
                strokeWidth=".08"
              />
              <text
                x={x + 0.5}
                y={y + 0.78}
                textAnchor="middle"
                fill="#15252d"
                fontSize=".8"
                fontWeight="700"
              >
                0{i}
              </text>
              <title>{i === 0 ? "Launch depot" : "Delivery target " + i}</title>
            </g>
          ))}
          {revealed && drone && (
            <g transform={`translate(${drone[0] + 0.5} ${drone[1] + 0.5})`}>
              <circle r=".55" fill="#15252d" stroke="white" strokeWidth=".12" />
              <path
                d="M-.3 .2L0-.35 .3 .2 0 .08z"
                fill="#7cff00"
                transform={`rotate(${angle})`}
              />
              <title>Single drone on actual grid path</title>
            </g>
          )}
        </g>
      </svg>
      {controlsHost &&
        createPortal(
          <div className="mission-playback">
            <button
              onClick={() => {
                playback.current.paused = !paused;
                setPaused(!paused);
              }}
            >
              {paused ? "Resume" : "Pause"}
            </button>
            <button
              disabled={
                !canReplay ||
                stage === "Classical Dijkstra exploration" ||
                stage.startsWith("QAOA ·")
              }
              onClick={() => void animate(events.length, "Search replay")}
            >
              Replay Search
            </button>
            <button
              disabled={!route}
              onClick={() =>
                void animate(path.length - 1, "Drone route playback")
              }
            >
              Replay Flight
            </button>
            <button
              onClick={() => {
                playback.current.epoch++;
                setProgress(0);
                setStage("Environment ready");
                playback.current.paused = false;
                setPaused(false);
                onReset();
              }}
            >
              Reset simulation
            </button>
            <label>
              Speed{" "}
              <select
                value={speed}
                onChange={(e) => {
                  const n = +e.target.value;
                  setSpeed(n);
                  playback.current.speed = n;
                }}
              >
                {[0.5, 1, 2, 4].map((s) => (
                  <option key={s} value={s}>
                    {s}×
                  </option>
                ))}
              </select>
            </label>
            <label>
              <input
                type="checkbox"
                checked={showGrid}
                onChange={(e) => setShowGrid(e.target.checked)}
              />{" "}
              Grid
            </label>
            <label>
              <input
                type="checkbox"
                checked={showSearch}
                onChange={(e) => setShowSearch(e.target.checked)}
              />{" "}
              Exploration
            </label>
          </div>,
          controlsHost,
        )}
      <p className="grid-note">
        Blue: explored · Sand: frontier · Lime: selected path. Classical
        Dijkstra: {(grid.search_seconds * 1000).toFixed(2)} ms · {grid.size} ×{" "}
        {grid.size} cells · {grid.step.toFixed(3)} units / step. Drag to pan.
        Playback time is separate from solver execution.
      </p>
    </>
  );
});
