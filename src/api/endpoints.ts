import { fetchJson } from "./http";
import type { CardSummary, EchoRequest, EchoResponse, HealthResponse } from "./types";

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
