import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  API_KEY_STORAGE,
  BASE_URL_STORAGE,
  clearKey,
  emit,
  getBaseUrl,
  getStoredKey,
  onUnauthorized,
  setBaseUrl,
  storeKey,
  DEFAULT_BASE_URL,
} from "./auth";

describe("api-key storage", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  afterEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  it("stores and clears the key while never touching localStorage", () => {
    storeKey("ssk_unit_test_key");
    expect(getStoredKey()).toBe("ssk_unit_test_key");
    expect(localStorage.getItem(API_KEY_STORAGE)).toBeNull();
    clearKey();
    expect(getStoredKey()).toBe("");
  });

  it("base URL defaults to localhost:8010 and honors overrides", () => {
    expect(getBaseUrl()).toBe(DEFAULT_BASE_URL);
    setBaseUrl("http://localhost:9010");
    expect(sessionStorage.getItem(BASE_URL_STORAGE)).toBe("http://localhost:9010");
    expect(getBaseUrl()).toBe("http://localhost:9010");
    setBaseUrl("");
    expect(getBaseUrl()).toBe(DEFAULT_BASE_URL);
  });
});

describe("unauthorized event bus", () => {
  afterEach(() => {
    emit("cleared");
  });

  it("notifies listeners for 401 and cleared", () => {
    const seen: string[] = [];
    const unsubscribe = onUnauthorized((reason) => seen.push(reason));
    emit("401");
    clearKey();
    unsubscribe();
    emit("401");
    expect(seen).toEqual(["401", "cleared"]);
  });
});

describe("storage discipline", () => {
  it("key lives only in sessionStorage, never cookies or localStorage", () => {
    storeKey("ssk_probe");
    expect(document.cookie).not.toContain("ssk_probe");
    expect(localStorage.getItem(API_KEY_STORAGE)).toBeNull();
    expect(sessionStorage.getItem(API_KEY_STORAGE)).toBe("ssk_probe");
    clearKey();
  });
});

// Silence unused import warning if vitest strips types differently across versions.
void vi;
