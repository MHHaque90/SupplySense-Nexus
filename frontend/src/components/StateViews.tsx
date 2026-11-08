import { ApiError } from "../api/client";

/**
 * Shared view states: loading, empty, unavailable-from-backend, error.
 * Error rendering is driven by the server error contract — no silent
 * failure can ever look like "no data".
 */

export function LoadingState({ message = "Loading from API…" }: { message?: string }) {
  return (
    <div className="state-block state-loading" role="status">
      <div className="spinner" aria-hidden="true" />
      <p>{message}</p>
    </div>
  );
}

export function EmptyState({ what, hint }: { what: string; hint?: string }) {
  return (
    <div className="state-block state-empty" role="status">
      <p className="state-title">No {what} available from the API</p>
      {hint ? <p className="state-hint">{hint}</p> : null}
      <p className="state-hint">This view shows data only when the backend returns it — the UI never invents values.</p>
    </div>
  );
}

export function ErrorState({
  error,
  what,
  onRetry,
}: {
  error: ApiError | null;
  what: string;
  onRetry?: () => void;
}) {
  return (
    <div className="state-block state-error" role="alert">
      <p className="state-title">The API request for {what} failed</p>
      <ErrorDetail error={error} />
      {onRetry ? (
        <button type="button" className="btn" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function ErrorDetail({ error }: { error: ApiError | null }) {
  if (!error) return <p className="state-hint">An unknown error occurred.</p>;
  const retryAfter =
    error.family === "rate_limited" && error.retryAfter
      ? ` Try again in ${error.retryAfter} second${error.retryAfter === 1 ? "" : "s"}.`
      : "";
  return (
    <ul className="error-detail">
      <li>
        <strong>Code:</strong> {error.code} <span className="muted">(HTTP {error.status || "network"})</span>
      </li>
      <li>
        <strong>Message:</strong> {error.message}
        {retryAfter}
      </li>
      {error.reason ? (
        <li>
          <strong>Reason:</strong> {error.reason}
        </li>
      ) : null}
    </ul>
  );
}

export function UnavailableState({
  title,
  reasons,
}: {
  title: string;
  reasons: string[];
}) {
  return (
    <div className="state-block state-unavailable" role="status">
      <p className="state-title">{title} is not available</p>
      {reasons.map((reason) => (
        <p key={reason} className="state-hint">
          {reason}
        </p>
      ))}
    </div>
  );
}

export function Limitations({ items }: { items: string[] | undefined }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="limitations-panel">
      <p className="limitations-title">Limitations (from API response)</p>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
