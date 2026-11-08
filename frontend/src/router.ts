import { useEffect, useState, type ReactElement } from "react";

/**
 * Minimal history-API router (no dependency).
 *
 * Supports: declarative route table with params, pathname parsing with
 * :param segments, navigate(), popstate/back-forward, 404 fallback, hashes
 * are not used (deep links work with Vite's SPA history fallback and
 * `vite preview`).
 */

export interface RouteDef {
  path: string; // "/suppliers/perf/:supplierId"
  render: (params: Record<string, string>) => ReactElement;
}

interface RouteMatch {
  route: RouteDef;
  params: Record<string, string>;
}

function matchPath(routePath: string, current: string): Record<string, string> | null {
  const routeParts = routePath.split("/").filter(Boolean);
  const currentParts = current.split("/").filter(Boolean);
  if (routeParts.length !== currentParts.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < routeParts.length; i++) {
    const rp = routeParts[i]!;
    const cp = currentParts[i]!;
    if (rp.startsWith(":")) {
      params[rp.slice(1)] = decodeURIComponent(cp);
    } else if (rp !== cp) {
      return null;
    }
  }
  return params;
}

export function currentPath(): string {
  const path = window.location.pathname;
  return path === "" ? "/" : path;
}

export function navigate(path: string, replace = false): void {
  if (replace) {
    window.history.replaceState({}, "", path);
  } else {
    window.history.pushState({}, "", path);
  }
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function useLocation(): string {
  const [path, setPath] = useState(currentPath());
  useEffect(() => {
    const onPop = () => setPath(currentPath());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  return path;
}

export function matchRoute(routes: RouteDef[], path: string): RouteMatch | null {
  for (const route of routes) {
    const params = matchPath(route.path, path);
    if (params) return { route, params };
  }
  return null;
}
