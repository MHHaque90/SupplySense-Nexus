import { type ApiEnvelope, type ApiErrorBody, type Meta } from "./types";
import { getBaseUrl, getStoredKey, emit } from "./auth";

/**
 * Typed API client for the Phase 12A contract.
 *
 * Every network call in the application passes through `request()`.
 * - injects `Authorization: Bearer <key>` when a key is stored;
 * - unwraps the success envelope and returns `{data, meta}`;
 * - converts every failure (non-2xx, malformed body, network failure,
 *   success=false) into a typed `ApiError` with the server error code;
 * - never logs or embeds the API key anywhere.
 */

export type ErrorFamily =
  | "unauthorized" // 401 — missing/malformed/unknown/deactivated key
  | "forbidden" // 403 — insufficient role
  | "validation" // 422 — bad request
  | "rate_limited" // 429 — Retry-After available
  | "server" // 5xx
  | "network" // fetch threw / backend unreachable
  | "malformed" // unparseable or unexpected response body
  | "api"; // any other success=false envelope

const FAMILY_BY_CODE: Record<string, ErrorFamily> = {
  UNAUTHORIZED: "unauthorized",
  FORBIDDEN: "forbidden",
  VALIDATION_ERROR: "validation",
  RATE_LIMIT_EXCEEDED: "rate_limited",
  INTERNAL_ERROR: "server",
  AI_UNAVAILABLE: "server",
  MALFORMED: "malformed",
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly family: ErrorFamily;
  readonly details: ApiErrorBody["details"];
  readonly retryAfter: number | null;
  /** Human-usable message: prefers server-provided details.reason (422 texts). */
  readonly reason: string | null;

  constructor(
    status: number,
    code: string,
    serverMessage: string,
    options: {
      details?: ApiErrorBody["details"];
      retryAfter?: number | null;
    } = {},
  ) {
    const family = FAMILY_BY_CODE[code] ?? (status === 0 ? "network" : status >= 500 ? "server" : "api");
    super((options.details?.reason && options.details.reason) || serverMessage || code);
    this.name = "ApiError";
    this.status = status;
    this.code = code || (status === 0 ? "NETWORK" : "UNKNOWN");
    this.family = family;
    this.details = options.details;
    this.retryAfter = options.retryAfter ?? null;
    this.reason = options.details?.reason ?? null;
  }
}

export interface ApiOk<T> {
  data: T;
  meta: Meta;
}

export interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
}

export function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const base = getBaseUrl().replace(/\/+$/, "");
  const url = new URL(base + "/api/v1" + path);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === "") continue;
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<ApiOk<T>> {
  const url = buildUrl(path, options.query);
  const key = getStoredKey();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (key) headers.Authorization = `Bearer ${key}`;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "NETWORK", "Backend is unreachable.", {
      details: { reason: "Requests failed. Is the API server running?" },
    });
  }

  let envelope: ApiEnvelope<T>;
  try {
    envelope = (await response.json()) as ApiEnvelope<T>;
  } catch {
    emit("invalid");
    throw new ApiError(
      response.status,
      "MALFORMED",
      "The server returned an unparseable response.",
      { details: { reason: "Response body is not valid JSON." } },
    );
  }

  if (!envelope || typeof envelope !== "object" || typeof envelope.success !== "boolean") {
    throw new ApiError(
      response.status,
      "MALFORMED",
      "The server response does not match the API envelope.",
      { details: { reason: "Missing success field in response envelope." } },
    );
  }

  if (!envelope.success || envelope.error) {
    const error = envelope.error ?? { code: "UNKNOWN", message: "Request failed without an error body." };
    const retryAfterHeader = response.headers.get("Retry-After");
    const retryAfter = retryAfterHeader === null ? null : Number(retryAfterHeader);
    if (FAMILY_BY_CODE[error.code] === "unauthorized") emit("401");
    throw new ApiError(response.status, error.code, error.message, {
      details: error.details,
      retryAfter: Number.isFinite(retryAfter) ? retryAfter : null,
    });
  }

  if (envelope.data === undefined) {
    throw new ApiError(
      response.status,
      "MALFORMED",
      "The server response is missing the data field.",
      { details: { reason: "Success envelope has no data." } },
    );
  }

  return {
    data: envelope.data,
    meta: (envelope.meta ?? { timestamp: "", data_source_label: "derived" }) as Meta,
  };
}

/* Convenience helpers used by pages. */

export function get<T>(path: string, query?: RequestOptions["query"], signal?: AbortSignal): Promise<ApiOk<T>> {
  return request<T>(path, { query, signal });
}

export function post<T>(path: string, body: unknown): Promise<ApiOk<T>> {
  return request<T>(path, { method: "POST", body });
}
