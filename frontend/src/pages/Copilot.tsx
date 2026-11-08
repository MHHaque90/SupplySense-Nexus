import { useState } from "react";
import { DataSourceLabelChip } from "../components/DataSourceLabel";
import { PageGate } from "../components/PageGate";
import { DataTable } from "../components/DataTable";
import { Section } from "../components/Ui";
import { ErrorState, Limitations, LoadingState } from "../components/StateViews";
import { endpoints } from "../api/endpoints";
import { useApiQuery } from "../state/useApiQuery";
import { ApiError } from "../api/client";


/**
 * AI Copilot — Phase 11 endpoints (/ai/chat, /ai/tools, /ai/approval).
 * Evidence, limitations and approval state are rendered straight from API
 * responses. Approval buttons only record a decision in the audit trail;
 * they never execute anything.
 */

interface ChatTurn {
  role: "user" | "assistant";
  text: string;
  meta?: ChatResponseMeta;
}

interface ChatResponseMeta {
  confidence: number;
  evidence: unknown[];
  limitations: string[];
  approved: boolean;
  provider: string;
  approval_ids: string[];
  conversation_id: string | null;
  data_source_label: string;
}

export function CopilotPage() {
  return (
    <PageGate>
      <CopilotBody />
    </PageGate>
  );
}

function CopilotBody() {
  const tools = useApiQuery(() => endpoints.aiTools(), []);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<ApiError | null>(null);
  const approvalState = useApproval();

  const send = async () => {
    const message = draft.trim();
    if (!message || sending) return;
    setTurns((t) => [...t, { role: "user", text: message }]);
    setDraft("");
    setSending(true);
    setSendError(null);
    try {
      const ok = await endpoints.aiChat(message, conversationId);
      setConversationId(ok.meta.conversation_id ?? conversationId);
      setTurns((t) => [
        ...t,
        {
          role: "assistant",
          text: ok.data.response,
          meta: {
            confidence: ok.data.confidence,
            evidence: ok.data.evidence,
            limitations: ok.data.limitations,
            approved: ok.data.approved,
            provider: ok.meta.provider ?? "unknown",
            approval_ids: ok.meta.approval_ids ?? [],
            conversation_id: ok.meta.conversation_id ?? null,
            data_source_label: ok.meta.data_source_label,
          },
        },
      ]);
      approvalState.register(ok.meta.approval_ids ?? []);
    } catch (err) {
      setSendError(err instanceof ApiError ? err : new ApiError(0, "UNKNOWN", String(err)));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>AI Copilot</h1>
        <span className="muted">Phase 11 assistant over the organization's own analytics tools</span>
        <DataSourceLabelChip label="derived" />
      </div>

      <Section
        title="Conversation"
        subtitle="Answers come with the provider's own confidence, evidence and limitations. No recommendation is ever invented by the UI."
        actions={conversationId ? <span className="muted small mono">conversation {conversationId.slice(0, 8)}…</span> : undefined}
      >
        {turns.length === 0 ? (
          <p className="muted">
            Ask about demand, forecasts, inventory health, supplier delivery or data quality. The
            assistant runs tools against your organization's synthetic dataset and reports evidence.
          </p>
        ) : (
          <div className="chat-log">
            {turns.map((turn, index) =>
              turn.role === "user" ? (
                <div key={index} className="chat-bubble user">{turn.text}</div>
              ) : (
                <div key={index} className="chat-bubble assistant">
                  <div>{turn.text}</div>
                  {turn.meta ? (
                    <div style={{ marginTop: 8 }}>
                      <div className="meta-row">
                        <DataSourceLabelChip label={turn.meta.data_source_label} />
                        <span className="chip chip-neutral">provider: {turn.meta.provider}</span>
                        <span className="chip chip-neutral">confidence: {turn.meta.confidence.toFixed(2)}</span>
                        {(() => {
                          const ids = turn.meta.approval_ids;
                          const hasApproved = ids.length > 0 && ids.every((id) => approvalState.pending.get(id) === "approved");
                          const hasRejected = ids.length > 0 && ids.some((id) => approvalState.pending.get(id) === "rejected");
                          const isApproved = hasApproved || (ids.length === 0 && turn.meta.approved);
                          if (hasRejected) {
                            return <span className="chip chip-bad">rejected</span>;
                          }
                          return isApproved ? (
                            <span className="chip chip-good">approved</span>
                          ) : (
                            <span className="chip chip-warn">not approved</span>
                          );
                        })()}
                      </div>
                      {turn.meta.evidence.length > 0 ? (
                        <>
                          <p className="state-hint" style={{ textAlign: "left", margin: "8px 0 2px" }}>Evidence attached:</p>
                          <ul className="evidence-list">
                            {turn.meta.evidence.map((e, i) => (
                              <li key={i}>{typeof e === "string" ? e : JSON.stringify(e)}</li>
                            ))}
                          </ul>
                        </>
                      ) : (
                        <p className="muted small" style={{ marginTop: 6 }}>No tool evidence was attached to this answer.</p>
                      )}
                      <Limitations items={turn.meta.limitations} />
                    </div>
                  ) : null}
                </div>
              ),
            )}
          </div>
        )}

        <div className="center-row" style={{ justifyContent: "flex-start", marginTop: 12, gap: 8 }}>
          <label className="field" style={{ flex: 1 }}>
            <span>Message</span>
            <input
              value={draft}
              placeholder="e.g. Which products are at risk of stockout next week?"
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              disabled={sending}
            />
          </label>
          <button type="button" className="btn btn-primary" onClick={() => void send()} disabled={sending || draft.trim() === ""}>
            {sending ? "Thinking…" : "Send"}
          </button>
          <button type="button" className="btn" onClick={() => { setTurns([]); setConversationId(null); setSendError(null); }} disabled={sending}>
            Reset conversation
          </button>
        </div>
        {sending ? <LoadingState message="Waiting for the assistant…" /> : null}
        {sendError ? (
          <ErrorState
            error={sendError}
            what="the AI chat request"
          />
        ) : null}
      </Section>

      {approvalState.pending.size > 0 ? (
        <Section
          title="Approvals"
          subtitle="Decisions are recorded in the audit trail and never executed. Status reflects the latest chat response and your decisions."
        >
          <DataTable
            columns={[
              { header: "Approval", render: (a: { approval_id: string; status: string }) => <code className="short-id">{a.approval_id}</code> },
              { header: "Status", render: (a) => statusChip(a.status) },
              {
                header: "Decision",
                render: (a) => {
                  if (a.status !== "pending") {
                    return <span className="muted small">decided: {a.status}</span>;
                  }
                  return (
                    <div style={{ display: "flex", gap: 6 }}>
                      <button type="button" className="btn btn-sm" onClick={() => approvalState.decide(a.approval_id, "approve")}>Approve</button>
                      <button type="button" className="btn btn-sm btn-danger" onClick={() => approvalState.decide(a.approval_id, "reject")}>Reject</button>
                    </div>
                  );
                },
              },
            ]}
            rows={Array.from(approvalState.pending.entries()).map(([approval_id, status]) => ({ approval_id, status }))}
          />
        </Section>
      ) : null}

      <Section title="Available tools" subtitle="From GET /ai/tools — what the assistant can execute on request">
        {tools.status === "loading" ? <LoadingState /> : null}
        {tools.status === "error" ? <ErrorState error={tools.error} what="the tool registry" /> : null}
        {tools.status === "empty" ? <p className="muted">No tools registered.</p> : null}
        {tools.status === "ok" ? (
          <>
            <p className="muted small">{tools.data.count} tools · requires_approval flags shown per tool</p>
            <DataTable
              columns={[
                { header: "Tool", render: (t: (typeof tools.data.tools)[0]) => <strong className="mono">{t.name}</strong> },
                { header: "Category", render: (t) => t.category },
                { header: "Executable", render: (t) => (t.executable ? "yes" : "no") },
                { header: "Requires approval", render: (t) => (t.requires_approval ? <span className="chip chip-warn">yes</span> : "no") },
                { header: "Description", render: (t) => <span className="small">{t.description}</span> },
              ]}
              rows={tools.data.tools}
            />
          </>
        ) : null}
      </Section>
    </div>
  );
}

export function useApproval() {
  const [pending, setPending] = useState<Map<string, "pending" | "approved" | "rejected">>(new Map());
  const [error, setError] = useState<string | null>(null);

  // Chat responses surface new approval ids via meta; the pending list is
  // component-scoped (never module-level) so it cannot survive across
  // navigations or be shared between users, and statuses are never invented
  // client-side: an id enters as "pending" and leaves only as decided.
  const register = (ids: string[]) => {
    setPending((map) => {
      const next = new Map(map);
      for (const id of ids) {
        if (!next.has(id)) next.set(id, "pending");
      }
      return next;
    });
  };

  const decide = async (approvalId: string, decision: "approve" | "reject") => {
    try {
      await endpoints.aiApproval(approvalId, decision);
      // The API recorded the decision (HTTP 200); mirror it locally so the
      // UI never shows a decided approval as still pending.
      setPending((map) => {
        const next = new Map(map);
        next.set(approvalId, decision === "approve" ? "approved" : "rejected");
        return next;
      });
      setError(null);
    } catch (err) {
      // A failed decision leaves every approval exactly as it was.
      setError(err instanceof ApiError ? `${err.code}: ${err.message}` : String(err));
    }
  };

  return { pending, error, register, decide };
}

function statusChip(status: string) {
  const kind = status === "approved" ? "chip-good" : status === "rejected" ? "chip-bad" : "chip-warn";
  return <span className={`chip ${kind}`}>{status}</span>;
}
