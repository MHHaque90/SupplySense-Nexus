import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, buildUrl, request } from "./client";
import { clearKey, getBaseUrl, getStoredKey, onUnauthorized, API_KEY_STORAGE, BASE_URL_STORAGE, DEFAULT_BASE_URL } from "./auth";

const okEnvelope = (data: unknown) => ({ success: true, data, meta: { timestamp: "t", data_source_label: "derived" } });

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

describe("client", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  it("sends Authorization header and unwraps success envelopes", async () => {
    storeKeyFor("k-test-1");
    const fetchMock = vi.fn(async () => jsonResponse(200, okEnvelope({ hello: 1 })));
    vi.stubGlobal("fetch", fetchMock);

    const result = await request<{ hello: number }>("/auth/me");

    expect(result.data).toEqual({ hello: 1 });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(DEFAULT_BASE_URL + "/api/v1/auth/me");
    expect(init?.headers).toMatchObject({ Authorization: "Bearer k-test-1" });
  });

  it("omits Authorization when no key is stored", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, okEnvelope({})));
    vi.stubGlobal("fetch", fetchMock);
    await request("/health");
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect((init?.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("maps 401 to the unauthorized family and emits 401", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(401, {
        success: false,
        error: { code: "UNAUTHORIZED", message: "Unknown API key." },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    let reason = "";
    clearKey();
    const unsubscribe = onUnauthorized((r) => {
      reason = r;
    });
    await expect(request("/dashboard/overview")).rejects.toMatchObject({
      family: "unauthorized",
      status: 401,
      code: "UNAUTHORIZED",
    });
    expect(reason).toBe("401");
    unsubscribe();
  });

  it("maps 403 to forbidden", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(403, { success: false, error: { code: "FORBIDDEN", message: "Requires planner role." } }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(request("/simulation/run")).rejects.toMatchObject({ family: "forbidden", status: 403 });
  });

  it("maps 422 to validation and prefers details.reason in the message", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(422, {
        success: false,
        error: { code: "VALIDATION_ERROR", message: "validation failed", details: { reason: "MIN_HORZ: horizon must be >= 1" } },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const failure = await request("/simulation/run").catch((e: unknown) => e as ApiError);
    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).family).toBe("validation");
    expect((failure as ApiError).message).toBe("MIN_HORZ: horizon must be >= 1");
  });

  it("reads Retry-After on 429", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(429, { success: false, error: { code: "RATE_LIMIT_EXCEEDED", message: "rate limited" } }, { "Retry-After": "37" }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const failure = (await request("/simulation/run").catch((e: unknown) => e)) as ApiError;
    expect(failure.family).toBe("rate_limited");
    expect(failure.retryAfter).toBe(37);
  });

  it("maps fetch failure to network family", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("failed to fetch"))));
    await expect(request("/health")).rejects.toMatchObject({ family: "network", code: "NETWORK" });
  });

  it("classifies unparseable bodies as malformed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("<html>proxy error</html>", { status: 502 })),
    );
    await expect(request("/health")).rejects.toMatchObject({ family: "malformed", code: "MALFORMED" });
  });

  it("classifies non-envelope JSON as malformed", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(200, { hello: "not an envelope" })));
    await expect(request("/health")).rejects.toMatchObject({ family: "malformed" });
  });

  it("POST requests carry JSON content type and body", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, okEnvelope({ ok: true })));
    vi.stubGlobal("fetch", fetchMock);
    await request("/ai/chat", { method: "POST", body: { message: "hi" } });
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe(JSON.stringify({ message: "hi" }));
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("buildUrl skips null/undefined/empty query params", () => {
    const url = buildUrl("/forecast", { page: 2, page_size: 10, search: "", skip: undefined, other: null });
    expect(url).toContain("page=2");
    expect(url).toContain("page_size=10");
    expect(url).not.toContain("search");
    expect(url).not.toContain("skip");
    expect(url).not.toContain("other");
  });

  it("buildUrl respects a stored base-url override", () => {
    sessionStorage.setItem(BASE_URL_STORAGE, "http://localhost:9999/");
    expect(buildUrl("/health")).toBe("http://localhost:9999/api/v1/health");
    sessionStorage.removeItem(BASE_URL_STORAGE);
    expect(getBaseUrl()).toBe(DEFAULT_BASE_URL);
  });
});

function storeKeyFor(key: string): void {
  sessionStorage.setItem(API_KEY_STORAGE, key);
}

describe("auth storage", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it("stores and clears the key without touching localStorage", () => {
    storeKeyFor("k-abc");
    expect(getStoredKey()).toBe("k-abc");
    expect(localStorage.getItem(API_KEY_STORAGE)).toBeNull();
    clearKey();
    expect(getStoredKey()).toBe("");
  });

  it("start with the default base URL and react to overrides", () => {
    expect(getBaseUrl()).toBe(DEFAULT_BASE_URL);
    sessionStorage.setItem(BASE_URL_STORAGE, "http://localhost:9010");
    expect(getBaseUrl()).toBe("http://localhost:9010");
    sessionStorage.removeItem(BASE_URL_STORAGE);
  });
});
