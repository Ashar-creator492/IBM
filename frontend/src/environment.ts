import { useRef, useState } from "react";
export type Cell = [number, number];
export type Environment = {
  size: number;
  revision: number;
  nodes: Cell[];
  obstacles: Cell[];
  zones: { center: Cell; radius: number }[];
  pathfinding: "dijkstra";
};
export const cellBlocked = (env: Environment, [x, y]: Cell) =>
  env.obstacles.some((c) => c[0] === x && c[1] === y) ||
  env.zones.some(
    (z) =>
      Math.max(Math.abs(x - z.center[0]) - 0.5, 0) ** 2 +
        Math.max(Math.abs(y - z.center[1]) - 0.5, 0) ** 2 <=
      z.radius ** 2,
  );
export function moveCheckpoint(
  env: Environment,
  index: number,
  cell: Cell,
): Environment {
  if (
    cell.some((v) => v < 0 || v >= env.size) ||
    cellBlocked(env, cell) ||
    env.nodes.some(
      (c, i) => i !== index && c[0] === cell[0] && c[1] === cell[1],
    )
  )
    throw Error(
      "Invalid placement: choose a free cell outside EW zones and other checkpoints.",
    );
  return { ...env, nodes: env.nodes.map((c, i) => (i === index ? cell : c)) };
}
export function paintCells(
  env: Environment,
  cells: Cell[],
  erase = false,
): Environment {
  if (
    !erase &&
    cells.some((c) => env.nodes.some((n) => n[0] === c[0] && n[1] === c[1]))
  )
    throw Error("Cannot draw an obstacle over a checkpoint.");
  const blocked = new Map(env.obstacles.map((c) => [c.join(","), c]));
  for (const c of cells) {
    if (c.some((v) => v < 0 || v >= env.size)) continue;
    if (erase) blocked.delete(c.join(","));
    else blocked.set(c.join(","), c);
  }
  return { ...env, obstacles: [...blocked.values()] };
}
export function useEnvironment(onInvalidate: () => void) {
  const [environment, setEnvironment] = useState<Environment | null>(null);
  const history = useRef<Environment[]>([]),
    future = useRef<Environment[]>([]),
    original = useRef<Environment | null>(null),
    revision = useRef(0);
  const commit = (env: Environment, record = true) => {
    onInvalidate();
    if (record && environment) {
      history.current = [...history.current, environment].slice(-50);
      future.current = [];
    }
    const next = reviseEnvironment(env, ++revision.current);
    setEnvironment(next);
    return next;
  };
  return {
    environment,
    commit,
    load: (env: Environment) => {
      original.current = structuredClone(env);
      history.current = [];
      future.current = [];
      commit(env, false);
    },
    reset: () => {
      if (original.current) commit(structuredClone(original.current));
    },
    restoreNodes: () => {
      if (original.current && environment)
        commit({
          ...environment,
          nodes: structuredClone(original.current.nodes),
        });
    },
    resetZones: () => {
      if (original.current && environment)
        commit({
          ...environment,
          zones: structuredClone(original.current.zones),
        });
    },
    undo: () => {
      const previous = history.current.pop();
      if (previous && environment) {
        future.current.push(environment);
        commit(previous, false);
      }
    },
    redo: () => {
      const next = future.current.pop();
      if (next && environment) {
        history.current.push(environment);
        commit(next, false);
      }
    },
    canUndo: history.current.length > 0,
    canRedo: future.current.length > 0,
  };
}

export function reviseEnvironment(
  env: Environment,
  revision: number,
): Environment {
  return { ...env, revision };
}
export function revisionMatches(
  reply: { revision: number },
  env: { revision: number },
) {
  return reply.revision === env.revision;
}
