import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { endpoints } from "../api/endpoints";
import {
  clearKey,
  getStoredKey,
  onUnauthorized,
  storeKey,
} from "../api/auth";
import { ApiError } from "../api/client";
import type { AuthIdentity } from "../api/types";

/**
 * Authentication state, driven strictly by the backend:
 * - key presence in sessionStorage starts as "unknown";
 * - `GET /auth/me` validates it; data comes from the API only
 *   (no fabricated identity or role);
 * - any 401 marks the key invalid (uniform UNAUTHORIZED contract);
 * - cleared key returns to "no-key".
 */

export type AuthStatus = "no-key" | "validating" | "authenticated" | "invalid";

export interface AuthState {
  status: AuthStatus;
  identity: AuthIdentity | null;
  error: string | null;
  setKey: (apiKey: string) => Promise<boolean>;
  clear: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>(() => (getStoredKey() ? "validating" : "no-key"));
  const [identity, setIdentity] = useState<AuthIdentity | null>(null);
  const [error, setError] = useState<string | null>(null);

  const validate = useCallback(async () => {
    if (!getStoredKey()) {
      setStatus("no-key");
      setIdentity(null);
      setError(null);
      return;
    }
    setStatus("validating");
    try {
      const ok = await endpoints.me();
      setIdentity(ok.data);
      setError(null);
      setStatus("authenticated");
    } catch (err) {
      setIdentity(null);
      const apiError = err instanceof ApiError ? err : null;
      if (apiError?.family === "unauthorized") {
        setStatus("invalid");
        setError("The stored API key was rejected by the backend.");
      } else if (apiError?.family === "network") {
        setStatus("validating");
        setError("Backend unreachable — identity cannot be verified yet.");
      } else {
        setStatus("validating");
        setError(apiError ? apiError.message : "Identity verification failed.");
      }
    }
  }, []);

  useEffect(() => {
    void validate();
  }, [validate]);

  useEffect(() => {
    return onUnauthorized((reason) => {
      if (reason === "cleared") {
        setStatus("no-key");
        setIdentity(null);
        setError(null);
        return;
      }
      setStatus("invalid");
      setIdentity(null);
      setError(reason === "401" ? "The stored API key was rejected by the backend." : "Key rejected.");
    });
  }, []);

  const setKey = useCallback(
    async (apiKey: string): Promise<boolean> => {
      storeKey(apiKey);
      await validate();
      return true;
    },
    [validate],
  );

  const clear = useCallback(() => {
    clearKey();
    setIdentity(null);
    setError(null);
    setStatus("no-key");
  }, []);

  const value = useMemo<AuthState>(
    () => ({ status, identity, error, setKey, clear, refresh: validate }),
    [status, identity, error, setKey, clear, validate],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
