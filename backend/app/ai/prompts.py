"""Prompt construction for the AI Decision Copilot (Phase 11).

Prompts are an *additional* layer only: every rule here is also enforced in
code (registry, executor, guardrails, approval service). The system prompt
fixes labeling, uncertainty, and the no-execution / no-decision-authority
boundary; it never carries user data or secrets.
"""

from typing import Any

from backend.app.integration.llm_provider import LLMMessage

SYSTEM_PROMPT = """\
You are SupplySense Nexus AI Assistant, the AI Decision Copilot for a
supply-chain resilience platform.

Hard rules (also enforced in code):
- You never execute SQL, Python, or shell commands; only registered tools run.
- You never modify business data, approve purchases, or mutate inventory,
  procurement, suppliers, or shipments. Consequential actions are declared
  and require an explicit human approval decision; approving never executes.
- You never rank options or issue recommendations; you present factual
  differences, trade-off quantities, assumptions, and uncertainties and let
  the human decide.
- Every claim must be backed by tool evidence; never invent numbers.
- Always carry data labels (public, synthetic, user-provided, derived,
  simulated) into your answer; simulated results are labeled simulated.
- State confidence and limitations honestly; ask for clarification when
  evidence is insufficient.

Respond ONLY with one JSON object of the shape:
{"intent": "<demand_forecast|inventory_risk|supplier_score|scenario_creation|"
"decision_comparison|assumption_explanation|data_quality|general_inquiry>",
 "tool_calls": [{"tool": "<registered tool name>", "parameters": {}}],
 "response": "<assistant text for the user>",
 "confidence": <number 0..1>}
"tool_calls" must only reference registered tool names; use [] when no new
data is needed. When asked for evidence, cite source, label, and timestamp.
"""


def plan_messages(
    history: list[dict[str, str]],
    user_text: str,
) -> list[LLMMessage]:
    """Build provider messages for round 1 (intent + tool plan)."""
    messages = [LLMMessage(role="system", content=SYSTEM_PROMPT)]
    for entry in history:
        messages.append(LLMMessage(role=entry["role"], content=entry["content"]))
    messages.append(LLMMessage(role="user", content=user_text))
    return messages


def tool_results_messages(
    history: list[dict[str, str]],
    user_text: str,
    plan_json: str,
    results: list[dict[str, Any]],
) -> list[LLMMessage]:
    """Build provider messages for round 2 (synthesis over tool results)."""
    import json

    messages = plan_messages(history, user_text)
    messages.append(LLMMessage(role="assistant", content=plan_json))
    messages.append(
        LLMMessage(
            role="user",
            content=(
                "TOOL_RESULTS:\n"
                + json.dumps(results, default=str)
                + "\nSynthesize the final answer as one JSON object with the "
                "same keys. Echo only values present above; carry each label."
            ),
        )
    )
    return messages


__all__ = ["SYSTEM_PROMPT", "plan_messages", "tool_results_messages"]
