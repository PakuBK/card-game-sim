import { fetchJson } from "./http";
import type { components } from "./generated/openapi";

export type HealthResponse = components["schemas"]["HealthResponse"];
export type SimulationSchemaResponse = components["schemas"]["SimulationSchemaResponse"];
export type SimulationRequest = components["schemas"]["SimulationRequest"];
export type SimulationResponse = components["schemas"]["SimulationResponse"];

export function getHealth(): Promise<HealthResponse> {
  return fetchJson<HealthResponse>("/api/health");
}

export function getSimulationSchema(): Promise<SimulationSchemaResponse> {
  return fetchJson<SimulationSchemaResponse>("/api/simulation/schema");
}

export function postSimulate(payload: SimulationRequest): Promise<SimulationResponse> {
  return fetchJson<SimulationResponse>("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
