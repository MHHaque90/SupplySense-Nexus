/**
 * API-key storage.
 *
 * SECURITY TRADEOFF (documented, intentional):
 * The Phase 12A contract authenticates every request with an opaque Bearer
 * API key. The key must live in the browser somewhere. This app uses
 * sessionStorage (per-tab, cleared when the tab closes) — the least
 * persistent mechanism that remains usable for this architecture:
 *
 * - never in localStorage (survives browser restarts);
 * - never in a cookie (would be sent to any same-origin request);
 * - never logged, never rendered outside a password-type input;
 * - never included in error messages or analytics.
 *
 * Residual risk: a successful XSS attack in this tab could read the key
 * while a session is open. Mitigations: no innerHTML/dangerouslySetInnerHTML
 * anywhere, no eval, no third-party scripts, no URL-parameter passing.
 */

export const API_KEY_STORAGE = "ssn.api_key";
export const BASE_URL_STORAGE = "ssn.base_url";

export const DEFAULT_BASE_URL = "http://localhost:8010";

const listeners = new Set<(reason: UnauthorizedReason | "cleared") => void>();

export type UnauthorizedReason = "401" | "invalid";

export function getStoredKey(): string {
  return sessionStorage.getItem(API_KEY_STORAGE) ?? "";
}

export function storeKey(apiKey: string): void {
  sessionStorage.setItem(API_KEY_STORAGE, apiKey);
}

export function clearKey(): void {
  sessionStorage.removeItem(API_KEY_STORAGE);
  emit("cleared");
}

export function getBaseUrl(): string {
  return sessionStorage.getItem(BASE_URL_STORAGE) || DEFAULT_BASE_URL;
}

export function setBaseUrl(base: string): void {
  if (base.trim() === "" || base === DEFAULT_BASE_URL) {
    sessionStorage.removeItem(BASE_URL_STORAGE);
  } else {
    sessionStorage.setItem(BASE_URL_STORAGE, base);
  }
}

export function onUnauthorized(listener: (reason: UnauthorizedReason | "cleared") => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function emit(reason: UnauthorizedReason | "cleared"): void {
  for (const listener of listeners) {
    listener(reason);
  }
}
