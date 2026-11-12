export interface RouteMap {
  nodes: number[][];
  threat_center: number[];
  threat_radius: number;
  unsafe_penalty: number;
  costs: number[][];
  unsafe_edges: boolean[][];
}
export interface Classical {
  route: number[];
  cost: number;
  safe: boolean;
  elapsed_seconds: number;
  tours_evaluated: number;
}
export interface Config {
  shots: number;
  maxiter: number;
  layers: number;
  seed: number;
}
export interface Result {
  mixer?: string;
  node_count?: number;
  formulation?: string;
  simulator_device?: string;
  qubits: number;
  circuit_depth: number;
  iterations: number;
  objective: number;
  ising_offset: number;
  parameters: number[];
  success: boolean;
  message: string;
  elapsed_seconds: number;
  shots: number;
  sampled_bitstring: string;
  sampled_route: number[] | null;
  sampled_reason: string | null;
  sampled_cost: number | null;
  sampled_safe: boolean | null;
  feasible_samples: number;
  best_feasible_bitstring: string | null;
  best_feasible_route: number[] | null;
  best_feasible_cost: number | null;
  best_feasible_safe: boolean | null;
  history: number[];
  layers: number;
  circuit_text: string;
  top_samples: {
    bitstring: string;
    count: number;
    feasible: boolean;
    reason: string | null;
  }[];
  matched_optimum: boolean;
}
export async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    "/api/" + path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : undefined,
  );
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(
      typeof data?.detail === "string"
        ? data.detail
        : `Request failed (${response.status}). Check the local API.`,
    );
  }
  return response.json() as Promise<T>;
}
