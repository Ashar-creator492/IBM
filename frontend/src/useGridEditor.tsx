import { useRef, useState } from "react";
import {
  moveCheckpoint,
  paintCells,
  type Environment,
  type Cell,
} from "./environment";
export function useGridEditor(
  env: Environment | null,
  onEdit: ((e: Environment) => void) | undefined,
  locked: boolean,
  onReset: () => void,
  onUndo: () => void,
  onRedo: () => void,
) {
  const [tool, setTool] = useState("move"),
    [selected, setSelected] = useState<number | null>(null),
    [zone, setZone] = useState(0),
    [warning, setWarning] = useState("");
  const drag = useRef<{
    kind: string;
    index: number;
    start: Cell;
    last: Cell;
  } | null>(null);
  const apply = (fn: () => Environment) => {
    try {
      onEdit?.(fn());
      setWarning("");
    } catch (e) {
      setWarning(e instanceof Error ? e.message : "Invalid edit");
    }
  };
  const down = (cell: Cell) => {
    if (!env || locked || tool === "pan") return false;
    setWarning("");
    const node = env.nodes.findIndex(
      (c) => c[0] === cell[0] && c[1] === cell[1],
    );
    const zoneIndex = env.zones.findIndex(
      (z) =>
        Math.hypot(z.center[0] - cell[0], z.center[1] - cell[1]) <= z.radius,
    );
    if (tool === "move") {
      if (node >= 0) {
        setSelected(node);
        drag.current = { kind: "node", index: node, start: cell, last: cell };
        return true;
      }
      if (zoneIndex >= 0) {
        setZone(zoneIndex);
        drag.current = {
          kind: "zone",
          index: zoneIndex,
          start: cell,
          last: cell,
        };
        return true;
      }
      return false;
    }
    if (tool === "zone") {
      if (env.zones.length >= 4) {
        setWarning("Maximum four EW zones.");
        return true;
      }
      apply(() => ({
        ...env,
        zones: [...env.zones, { center: cell, radius: 2 }],
      }));
      setZone(env.zones.length);
      return true;
    }
    drag.current = { kind: tool, index: 0, start: cell, last: cell };
    if (tool !== "rectangle")
      apply(() => paintCells(env, [cell], tool === "erase"));
    return true;
  };
  const move = (cell: Cell) => {
    const d = drag.current;
    if (!env || !d || locked) return;
    if (d.kind === "node") apply(() => moveCheckpoint(env, d.index, cell));
    else if (d.kind === "zone")
      apply(() => ({
        ...env,
        zones: env.zones.map((z, i) =>
          i === d.index ? { ...z, center: cell } : z,
        ),
      }));
    else if (d.kind !== "rectangle") {
      const count = Math.max(
        Math.abs(cell[0] - d.last[0]),
        Math.abs(cell[1] - d.last[1]),
      );
      const cells: Cell[] = Array.from({ length: count + 1 }, (_, i) => [
        Math.round(d.last[0] + ((cell[0] - d.last[0]) * i) / (count || 1)),
        Math.round(d.last[1] + ((cell[1] - d.last[1]) * i) / (count || 1)),
      ]);
      apply(() => paintCells(env, cells, d.kind === "erase"));
    }
    d.last = cell;
  };
  const up = (cell: Cell) => {
    const d = drag.current;
    if (env && d?.kind === "rectangle") {
      const cells: Cell[] = [];
      for (
        let x = Math.min(d.start[0], cell[0]);
        x <= Math.max(d.start[0], cell[0]);
        x++
      )
        for (
          let y = Math.min(d.start[1], cell[1]);
          y <= Math.max(d.start[1], cell[1]);
          y++
        )
          cells.push([x, y]);
      apply(() => paintCells(env, cells));
    }
    drag.current = null;
  };
  const z = env?.zones[zone];
  const controls = env && (
    <div className="environment-editor">
      <fieldset disabled={locked}>
        <div className="editor-tools">
          {[
            ["move", "Select / Move"],
            ["pan", "Pan"],
            ["draw", "Draw cells"],
            ["rectangle", "Draw rectangle"],
            ["erase", "Erase"],
            ["zone", "Add EW"],
          ].map(([id, label]) => (
            <button
              type="button"
              key={id}
              aria-pressed={tool === id}
              onClick={() => setTool(id)}
            >
              {label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => apply(() => ({ ...env, obstacles: [] }))}
          >
            Clear obstacles
          </button>
          <button type="button" onClick={onUndo}>
            Undo
          </button>
          <button type="button" onClick={onRedo}>
            Redo
          </button>
          <button type="button" onClick={onReset}>
            Reset Environment
          </button>
        </div>
        <div className="checkpoint-coordinates">
          {env.nodes.map((c, i) => (
            <button
              key={i}
              type="button"
              aria-pressed={selected === i}
              onClick={() => {
                setSelected(i);
                setTool("move");
              }}
            >
              0{i} ({c.join(", ")})
            </button>
          ))}
        </div>
        <div className="zone-settings">
          <label>
            EW zone{" "}
            <select value={zone} onChange={(e) => setZone(+e.target.value)}>
              {env.zones.map((_, i) => (
                <option key={i} value={i}>
                  EW {i + 1}
                </option>
              ))}
            </select>
          </label>
          {z && (
            <>
              <label>
                Radius{" "}
                <input
                  type="range"
                  min=".5"
                  max={env.size}
                  step=".5"
                  value={z.radius}
                  onChange={(e) =>
                    apply(() => ({
                      ...env,
                      zones: env.zones.map((v, i) =>
                        i === zone ? { ...v, radius: +e.target.value } : v,
                      ),
                    }))
                  }
                />
                <output>{z.radius.toFixed(1)}</output>
              </label>
              {[0, 1].map((axis) => (
                <label key={axis}>
                  {axis === 0 ? "X" : "Y"}{" "}
                  <input
                    type="number"
                    min="0"
                    max={env.size - 1}
                    step=".5"
                    value={z.center[axis]}
                    onChange={(e) => {
                      const value = +e.target.value;
                      if (value >= 0 && value < env.size)
                        apply(() => ({
                          ...env,
                          zones: env.zones.map((v, i) =>
                            i === zone
                              ? {
                                  ...v,
                                  center: v.center.map((n, a) =>
                                    a === axis ? value : n,
                                  ) as Cell,
                                }
                              : v,
                          ),
                        }));
                    }}
                  />
                </label>
              ))}
              <button
                type="button"
                onClick={() => {
                  apply(() => ({
                    ...env,
                    zones: env.zones.filter((_, i) => i !== zone),
                  }));
                  setZone(0);
                }}
              >
                Remove zone
              </button>
            </>
          )}
        </div>
      </fieldset>
      <p role="status" className={warning ? "red" : ""}>
        {warning ||
          "Drag a checkpoint or EW zone with Select / Move. Draw and erase affect real navigation."}
      </p>
    </div>
  );
  return {
    controls,
    selectTool: setTool,
    down,
    move,
    up,
    selected,
    tool,
    dragging: () => drag.current !== null,
    cancel: () => {
      drag.current = null;
    },
    selectedZone: zone,
  };
}
