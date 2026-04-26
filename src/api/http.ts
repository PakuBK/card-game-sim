import type { components } from "./generated/openapi";

export type ApiErrorResponse = components["schemas"]["ApiErrorResponse"];

export class HttpError extends Error {
  readonly status: number;
  readonly body: unknown;
  readonly rawText: string;

  constructor(message: string, status: number, body: unknown, rawText: string) {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.body = body;
    this.rawText = rawText;
  }
}

export function isHttpError(error: unknown): error is HttpError {
  return error instanceof HttpError;
}

export function asApiErrorResponse(body: unknown): ApiErrorResponse | undefined {
  if (!body || typeof body !== "object") return undefined;
  const candidate = body as { error?: unknown };
  if (!candidate.error || typeof candidate.error !== "object") return undefined;
  return body as ApiErrorResponse;
}

function errorMessageFromBody(body: unknown): string {
  const apiBody = asApiErrorResponse(body);
  if (apiBody?.error.message) return apiBody.error.message;
  if (body && typeof body === "object") {
    const message = (body as { message?: unknown }).message;
    if (typeof message === "string" && message.trim().length > 0) return message;
  }
  return "";
}

export async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const res = await fetch(input, init);
  if (!res.ok) {
    const rawText = await res.text().catch(() => "");
    let body: unknown;

    if (rawText) {
      try {
        body = JSON.parse(rawText) as unknown;
      } catch {
        body = undefined;
      }
    }

    const bodyMessage = errorMessageFromBody(body);
    const fallbackMessage = rawText.trim();
    const messageSuffix = bodyMessage || fallbackMessage;
    throw new HttpError(
      `HTTP ${res.status}${messageSuffix ? `: ${messageSuffix}` : ""}`,
      res.status,
      body,
      rawText,
    );
  }
  return (await res.json()) as T;
}
