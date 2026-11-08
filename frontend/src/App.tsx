import { Component, useEffect, type ErrorInfo, type ReactNode } from "react";
import { LabelLegend } from "./components/DataSourceLabel";
import { routes } from "./routes";
import { matchRoute, navigate, useLocation } from "./router";
import { useAuth } from "./state/AuthContext";

const PATH_BY_LABEL: Record<string, string> = {
  Overview: "/overview",
  Forecasts: "/forecasts",
  Inventory: "/inventory",
  Suppliers: "/suppliers",
  Procurement: "/procurement",
  Risk: "/risk",
  Simulation: "/simulation",
  "Decision Replay": "/replay",
  Optimization: "/optimization",
  "AI Copilot": "/copilot",
  Settings: "/settings",
};

export function App() {
  const path = useLocation();
  const auth = useAuth();

  useEffect(() => {
    if (path === "/") navigate("/overview", true);
  }, [path]);

  const match = matchRoute(routes, path);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">
          <button type="button" className="brand-btn" onClick={() => navigate("/overview")}>
            <span className="brand-mark" aria-hidden="true">◈</span>
            <span className="brand-text">SupplySense <strong>Nexus</strong></span>
          </button>
          <span className="brand-sub">Supply Chain Decision Intelligence</span>
        </div>
        <nav className="app-nav" aria-label="Primary">
          {Object.entries(PATH_BY_LABEL).map(([label, target]) => (
            <button
              key={target}
              type="button"
              className={`nav-item${path === target ? " active" : ""}`}
              aria-current={path === target ? "page" : undefined}
              onClick={() => navigate(target)}
            >
              {label}
            </button>
          ))}
        </nav>
        <IdentityBlock />
      </header>

      {auth.status === "invalid" ? (
        <div className="banner banner-error" role="alert">
          Your API key was rejected ({auth.error || "401 UNAUTHORIZED"}). Enter a valid key in Settings.
          <button type="button" className="btn btn-sm" onClick={() => navigate("/settings")}>
            Open Settings
          </button>
        </div>
      ) : null}
      {auth.status === "validating" && auth.error ? (
        <div className="banner banner-warn" role="status">
          {auth.error}
        </div>
      ) : null}

      <main className="app-main">
        <RouteErrorBoundary pathKey={path}>
          {match ? match.route.render(match.params) : <NotFound />}
        </RouteErrorBoundary>
      </main>

      <footer className="app-footer">
        <p>
          SupplySense Nexus visualizes the Phase 12A API contract. Synthetic / forecast / simulated
          outputs are labeled and are never presented as real operational data.
        </p>
        <LabelLegend />
      </footer>
    </div>
  );
}

function IdentityBlock() {
  const auth = useAuth();
  if (auth.status === "authenticated" && auth.identity) {
    const { email, role } = auth.identity;
    return (
      <div className="identity">
        <span className="identity-email" title={auth.identity.organization_id}>{email}</span>
        <span className="chip chip-role">{role}</span>
        <button type="button" className="btn btn-sm" onClick={() => auth.clear()}>
          Lock
        </button>
      </div>
    );
  }
  return (
    <div className="identity">
      {auth.status === "no-key" ? (
        <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate("/settings")}>
          Unlock with API key
        </button>
      ) : auth.status === "validating" ? (
        <span className="muted identity-email">verifying key…</span>
      ) : (
        <span className="chip chip-bad">key rejected</span>
      )}
    </div>
  );
}

function NotFound() {
  return (
    <div className="state-block">
      <p className="state-title">Page not found</p>
      <button type="button" className="btn" onClick={() => navigate("/overview")}>
        Go to Overview
      </button>
    </div>
  );
}

interface BoundaryProps {
  pathKey: string;
  children: ReactNode;
}

interface BoundaryState {
  error: Error | null;
}

/** Catches render-time errors so a page defect shows a diagnostic panel, never a blank app. */
class RouteErrorBoundary extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Route render error:", error, info.componentStack);
  }

  componentDidUpdate(prevProps: BoundaryProps): void {
    if (prevProps.pathKey !== this.props.pathKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="state-block" role="alert">
          <p className="state-title">Page failed to render</p>
          <p className="muted small mono">{this.state.error.message}</p>
          <p className="muted small">This is a frontend defect, not an API error. The trace is in the browser console.</p>
          <button type="button" className="btn" onClick={() => navigate("/overview")}>
            Go to Overview
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
