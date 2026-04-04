import { fetchJson } from "./http";
import type { components } from "./generated/openapi";

export type HealthResponse = components["schemas"]["HealthResponse"];
export type CardSummary = components["schemas"]["CardSummary"];
export type EchoRequest = components["schemas"]["EchoRequest"];
export type EchoResponse = components["schemas"]["EchoResponse"];

export function getHealth(): Promise<HealthResponse> {
  return fetchJson<HealthResponse>("/api/health");
}

export function getCards(): Promise<CardSummary[]> {
  return fetchJson<CardSummary[]>("/api/cards");
}

export function postEcho(payload: EchoRequest): Promise<EchoResponse> {
  return fetchJson<EchoResponse>("/api/echo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
