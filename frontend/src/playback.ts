/** Playback clock shared by exploration and drone movement; independent of rendering. */
export class PlaybackClock {
  paused = false;
  speed = 1;
  epoch = 0;
  value = 0;
  hold = 0;
  total = 0;
  rate = 1;
  stops: number[] = [];
  begin(total: number, rate: number, stops: number[] = []) {
    this.epoch++;
    this.value = 0;
    this.hold = 0;
    this.total = total;
    this.rate = rate;
    this.stops = [...stops].sort((a, b) => a - b);
    return this.epoch;
  }
  tick(milliseconds: number) {
    if (this.paused) return this.value;
    if (this.hold > 0) {
      this.hold = Math.max(0, this.hold - milliseconds);
      return this.value;
    }
    const next = Math.min(
      this.total,
      this.value + milliseconds * this.speed * this.rate,
    );
    const stop = this.stops.find((s) => s > this.value && s <= next);
    this.value = stop ?? next;
    if (stop !== undefined) this.hold = 650;
    return this.value;
  }
}

/** Reconstruct the live queue from recorded Dijkstra discoveries and settlements. */
export function searchFrame(
  pairs: {
    explored: [number, number][];
    frontier_steps: [number, number][][];
  }[],
  progress: number,
) {
  let remaining = Math.floor(progress);
  let pair = pairs[pairs.length - 1];
  for (const candidate of pairs) {
    pair = candidate;
    if (remaining < candidate.explored.length) break;
    if (candidate !== pairs[pairs.length - 1])
      remaining -= candidate.explored.length;
  }
  const count = Math.min(remaining, pair.explored.length);
  const frontier = new Map<string, [number, number]>();
  frontier.set(pair.explored[0].join(","), pair.explored[0]);
  for (let i = 0; i < count; i++) {
    frontier.delete(pair.explored[i].join(","));
    for (const cell of pair.frontier_steps[i])
      frontier.set(cell.join(","), cell);
  }
  return {
    explored: pair.explored.slice(0, count),
    frontier: [...frontier.values()],
  };
}

export function stitchRoute(
  route: number[] | null | undefined,
  pairs: { source: number; target: number; path: [number, number][] }[],
) {
  const path: [number, number][] = [],
    stops = new Set<number>();
  if (!route) return { path, stops };
  for (let i = 0; i < route.length - 1; i++) {
    const a = route[i],
      b = route[i + 1];
    const pair = pairs.find(
      (p) => p.source === Math.min(a, b) && p.target === Math.max(a, b),
    );
    if (!pair || !pair.path.length)
      return { path: [], stops: new Set<number>() };
    const leg = a === pair.source ? [...pair.path] : [...pair.path].reverse();
    if (path.length) leg.shift();
    path.push(...leg);
    stops.add(path.length - 1);
  }
  return { path, stops };
}
