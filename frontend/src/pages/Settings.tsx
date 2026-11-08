import { useState } from "react";
import { DataSourceLabelChip } from "../components/DataSourceLabel";
import { Section } from "../components/Ui";
import { navigate } from "../router";
import { useAuth } from "../state/AuthContext";
import { DEFAULT_BASE_URL, getBaseUrl, setBaseUrl, API_KEY_STORAGE, BASE_URL_STORAGE } from "../api/auth";
import { endpoints } from "../api/endpoints";

/**
 * Settings — API key entry and connection configuration.
 *
 * SECURITY (documented tradeoff): the key lives in this tab's sessionStorage
 * only. It is never logged, never rendered outside password-type inputs, and
 * cleared on tab close or via "Lock". The backend validates it on every
 * request with a constant-time comparison; there is no login/JWT contract.
 */
export function SettingsPage() {
  const auth = useAuth();
  const [keyDraft, setKeyDraft] = useState("");
  const [baseUrlDraft, setBaseUrlDraft] = useState(getBaseUrl());
  const [saving, setSaving] = useState(false);
  const [health, setHealth] = useState<string | null>(null);

  const onFinish = async () => {
    setSaving(true);
    setBaseUrl(baseUrlDraft.trim() === "" ? DEFAULT_BASE_URL : baseUrlDraft.trim());
    await auth.setKey(keyDraft.trim());
    setKeyDraft("");
    setSaving(false);
    navigate("/overview");
  };

  const probe = async () => {
    try {
      const ok = await endpoints.health();
      setHealth(`${ok.data.status} — ${ok.data.service} v${ok.data.version} (public /health endpoint)`);
    } catch {
      setHealth(null);
    }
  };
  void probe;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Settings</h1>
        <span className="muted">API connection and key management</span>
      </div>

      <Section title="API key" subtitle="The Phase 12A backend authenticates every request with an opaque Bearer key (prefix ssk_…). There is no username/password or JWT login.">
        {auth.status === "authenticated" && auth.identity ? (
          <>
            <p className="muted small">
              Authenticated via GET /auth/me as <strong>{auth.identity.email}</strong> — the UI shows identity
              only as the API reported it:
            </p>
            <div className="table-wrap">
              <table className="data-table">
                <tbody>
                  <tr><td>User</td><td className="mono">{auth.identity.email}</td></tr>
                  <tr><td>Role (from API)</td><td><span className="chip chip-role">{auth.identity.role}</span></td></tr>
                  <tr><td>Active</td><td>{String(auth.identity.is_active)}</td></tr>
                  <tr><td>Organization</td><td><code className="short-id">{auth.identity.organization_id}</code></td></tr>
                  <tr><td>Data-source label of identity response</td><td><DataSourceLabelChip label="derived" /></td></tr>
                </tbody>
              </table>
            </div>
            <div className="center-row" style={{ justifyContent: "flex-start" }}>
              <button type="button" className="btn btn-danger" onClick={() => auth.clear()}>
                Lock (clear key from this tab)
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="muted small">
              No authenticated identity is shown because none has been verified. If identity or role are
              unknown, the UI will not fabricate them.
            </p>
            <div className="filter-bar" style={{ alignItems: "flex-end" }}>
              <label className="field" style={{ minWidth: 380 }}>
                <span>API key (ssk_…)</span>
                <input
                  type="password"
                  value={keyDraft}
                  autoComplete="off"
                  placeholder="paste the key issued for your user"
                  onChange={(e) => setKeyDraft(e.target.value)}
                />
              </label>
              <button type="button" className="btn btn-primary" disabled={saving || keyDraft.trim() === ""} onClick={() => void onFinish()}>
                {saving ? "Verifying…" : "Save and verify"}
              </button>
            </div>
          </>
        )}
        {auth.status === "authenticated" || auth.status === "invalid" ? (
          <div className="center-row" style={{ justifyContent: "flex-start" }}>
            <label className="field" style={{ minWidth: 380 }}>
              <span>Replace key</span>
              <input
                type="password"
                value={keyDraft}
                autoComplete="off"
                placeholder="paste a new key"
                onChange={(e) => setKeyDraft(e.target.value)}
              />
            </label>
            <button type="button" className="btn" disabled={saving || keyDraft.trim() === ""} onClick={() => void onFinish()}>
              {saving ? "Verifying…" : "Replace"}
            </button>
          </div>
        ) : null}
        {auth.error ? <p className="state-hint" style={{ margin: "8px 0 0" }}>{auth.error}</p> : null}
      </Section>

      <Section title="API base URL" subtitle="Where the frontend sends requests. The backend must allow this page's origin (http://localhost:5173) in its CORS list.">
        <div className="filter-bar" style={{ alignItems: "flex-end" }}>
          <label className="field" style={{ minWidth: 380 }}>
            <span>Base URL</span>
            <input value={baseUrlDraft} onChange={(e) => setBaseUrlDraft(e.target.value)} />
          </label>
          <button type="button" className="btn" onClick={() => { setBaseUrl(baseUrlDraft.trim() || DEFAULT_BASE_URL); window.location.reload(); }}>
            Apply (reload)
          </button>
        </div>
        <p className="muted small">
          Default {DEFAULT_BASE_URL}. The URL is stored in sessionStorage too ({BASE_URL_STORAGE}), the API key
          under {API_KEY_STORAGE}. Neither value is sent anywhere else.
        </p>
      </Section>

      <Section title="Connection check" subtitle="GET /health is public — it can be probed without a key">
        {health ? (
          <p className="mono small">{health}</p>
        ) : (
          <p className="muted small">
            Probe triggered in dev only. Typical failure modes: backend not started
            (<code>python -m uvicorn backend.app.main:app --loop none --port 8010</code>) or CORS origin not allowed.
          </p>
        )}
      </Section>

      <Section title="Security notes">
        <ul className="evidence-list">
          <li>The API key is kept in sessionStorage (per tab; cleared on tab close) — not localStorage, not cookies.</li>
          <li>The key is never logged, never rendered in plain text, and never included in error messages.</li>
          <li>The app renders no raw HTML (no dangerouslySetInnerHTML), uses no eval, and loads no third-party scripts.</li>
          <li>401 clears to a rejected-key state; the identity shown always comes from GET /auth/me only.</li>
        </ul>
      </Section>
    </div>
  );
}
