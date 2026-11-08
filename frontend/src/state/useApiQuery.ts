import { useEffect, useState } from "react";
import { ApiError, type ApiOk } from "../api/client";

/**
 * Generic data-fetching hook for API-backed views.
 *
 * Distinguishes loading / ok / empty / error so no failed request can
 * silently render as "no data". Abort-safe across rapid param changes.
 */

export type QueryState<T> =
  | { status: "loading" }
  | { status: "ok"; data: T; meta: ApiOk<unknown>["meta"] }
  | { status: "empty"; meta: ApiOk<unknown>["meta"] }
  | { status: "error"; error: ApiError };

export function isEmptyOk(data: unknown): boolean {
  if (data === null || data === undefined) return true;
  if (Array.isArray(data)) return data.length === 0;
  if (typeof data === "object") {
    const items = (data as { items?: unknown[] }).items;
    if (Array.isArray(items) && items.length === 0) return true;
  }
  return false;
}

export function useApiQuery<T>(
  fetcher: () => Promise<ApiOk<T>>,
  deps: unknown[],
  options: { enabled?: boolean } = {},
): QueryState<T> {
  const enabled = options.enabled !== false;
  const [state, setState] = useState<QueryState<T>>({ status: "loading" });

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let cancelled = false;
    setState({ status: "loading" });
    fetcher()
      .then((ok) => {
        if (cancelled) return;
        if (isEmptyOk(ok.data)) {
          setState({ status: "empty", meta: ok.meta });
        } else {
          setState({ status: "ok", data: ok.data, meta: ok.meta });
        }
      })
      .catch((error: unknown) => {
        if (cancelled || (error instanceof DOMException && error.name === "AbortError")) return;
        if (error instanceof ApiError) {
          setState({ status: "error", error });
        } else {
          setState({
            status: "error",
            error: new ApiError(0, "UNKNOWN", String((error as Error)?.message ?? error)),
          });
        }
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
