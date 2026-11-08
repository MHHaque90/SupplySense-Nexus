import { type ReactNode } from "react";
import { navigate } from "../router";
import { useAuth } from "../state/AuthContext";
import { LoadingState, UnavailableState } from "./StateViews";

/**
 * Gate wrapper for API-backed views:
 * - no API key → unlock prompt (no fake identity, no fake data);
 * - key being validated → loading;
 * - key rejected → honest failure state pointing at Settings.
 */
export function PageGate({ children }: { children: ReactNode }) {
  const auth = useAuth();

  if (auth.status === "no-key") {
    return (
      <div className="page">
        <UnavailableState
          title="API access"
          reasons={[
            "This view requires a SupplySense Nexus API key (opaque Bearer key issued for your user).",
            "Open Settings to store a key — it is kept in this tab's sessionStorage only and cleared when the tab closes.",
          ]}
        />
        <div className="center-row">
          <button type="button" className="btn btn-primary" onClick={() => navigate("/settings")}>
            Enter API key
          </button>
        </div>
      </div>
    );
  }

  if (auth.status === "validating") {
    return (
      <div className="page">
        <LoadingState message="Verifying API key with GET /auth/me…" />
      </div>
    );
  }

  if (auth.status === "invalid") {
    return (
      <div className="page">
        <UnavailableState
          title="API access"
          reasons={[
            "The stored API key was rejected (401 UNAUTHORIZED — missing, malformed, unknown, or deactivated).",
            "Open Settings to replace it.",
          ]}
        />
        <div className="center-row">
          <button type="button" className="btn btn-primary" onClick={() => navigate("/settings")}>
            Open Settings
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

/** Role notice for planner+ (POST) endpoints while role is known. */
export function PlannerGate({
  children,
  action,
}: {
  children: ReactNode;
  action: string;
}) {
  const auth = useAuth();
  const role = auth.identity?.role;
  if (role === "analyst") {
    return (
      <div className="page">
        <UnavailableState
          title={action}
          reasons={[
            `This action requires the planner role or above; the API reports your role as "${role}".`,
            "The compute endpoints return 403 FORBIDDEN for analysts. Request elevated access from your organization admin.",
          ]}
        />
      </div>
    );
  }
  if (!role) {
    return (
      <div className="page">
        <UnavailableState
          title={action}
          reasons={["Your role is unknown because identity has not been verified — no role is assumed."]}
        />
      </div>
    );
  }
  return <>{children}</>;
}
