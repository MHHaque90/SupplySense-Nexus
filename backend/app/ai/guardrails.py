"""Deterministic guardrails for the AI Decision Copilot (Phase 11).

Two layers, both in code (never prompt-only):

1. **Input guardrails**: refuse prompt-injection / code-execution requests
   with a fixed message (HTTP 200, low confidence, audited).
2. **Output guardrails**: enforce the governance wording rule (no
   best/should/recommend*/preferred/top choice/rank* language — decision C2),
   redact anything key-shaped, and cap runaway output length. Removed
   sentences are reported in ``limitations`` so scrubbing is visible.

The copilot never executes SQL or Python; that is enforced by the tool
registry (only registered tools run) and mirrored here as an input refusal
pattern so users get a clear answer instead of a dead tool call.
"""

import re
from dataclasses import dataclass, field

MAX_OUTPUT_CHARS = 6000

REFUSAL_RESPONSE = (
    "I cannot act on that request. I only retrieve, simulate, and explain "
    "platform data through registered tools; I do not execute SQL, Python, "
    "or instructions that override these rules. Ask about forecasts, "
    "inventory, suppliers, data quality, simulated scenarios, replays, or "
    "optimization analysis instead."
)

#: Prompt-injection and code-execution attempts (case-insensitive).
INJECTION_PATTERNS: tuple[str, ...] = (
    r"ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+"
    r"(?:instructions|prompts|messages|rules)",
    r"disregard\s+(?:the|your|all)\s+(?:rules|instructions|guidelines)",
    r"reveal\s+(?:your|the)\s+(?:system\s+prompt|hidden\s+instructions)",
    r"print\s+(?:your|the)\s+(?:system\s+)?prompt",
    r"you\s+are\s+now\s+(?:an?\s+)?(?:unrestricted|different|jailbroken)",
    r"act\s+as\s+(?:an?\s+)?(?:unrestricted|unfiltered)\s+",
    r"forget\s+(?:everything|all\s+previous)\s+(?:you|instructions)",
    r"\bdrop\s+table\b",
    r"\bdelete\s+from\s+\w+",
    r";\s*(?:drop|delete|update|insert)\s+",
    r"execute\s+(?:this|the\s+following|arbitrary)\s+(?:sql|python|code)",
    r"run\s+(?:this|the\s+following)\s+(?:python|script|code)",
)

#: Governance wording banned by decision C2 (decision support, not decision
#: authority): no ranking language, no recommendation language.
GOVERNANCE_PATTERNS: tuple[str, ...] = (
    r"\btop\s+choice\b",
    r"\brecommend(?:ation|ations|ed|s|ing)?\b",
    r"\brank(?:ing|ings|ed|s)?\b",
    r"\bshould\b",
    r"\bbest\b",
    r"\bpreferred\b",
)

#: Anything key-shaped must never leave the API.
SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bsk-[A-Za-z0-9_-]{10,}\b", "[redacted-key]"),
    (r"\bssk_[A-Za-z0-9_-]{10,}\b", "[redacted-key]"),
    (r"\bBearer\s+[A-Za-z0-9._-]{10,}\b", "Bearer [redacted]"),
)

_INJECTION_RE = tuple(re.compile(pattern, re.IGNORECASE) for pattern in INJECTION_PATTERNS)
_GOVERNANCE_RE = tuple(
    re.compile(pattern, re.IGNORECASE) for pattern in GOVERNANCE_PATTERNS
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class InputVerdict:
    """Result of an input guardrail check."""

    blocked: bool
    reason: str | None = None


@dataclass
class OutputVerdict:
    """Result of an output guardrail scrub."""

    text: str
    removed_sentences: list[str] = field(default_factory=list)
    redactions: int = 0

    @property
    def notes(self) -> list[str]:
        """Human-readable scrub notes for the limitations list."""
        notes: list[str] = []
        if self.removed_sentences:
            notes.append(
                "Statements violating the governance wording rules were "
                f"removed by output guardrails ({len(self.removed_sentences)})."
            )
        if self.redactions:
            notes.append("Key-shaped values in the draft were redacted.")
        if len(self.text) >= MAX_OUTPUT_CHARS:
            notes.append("Output was truncated to the bounded response length.")
        return notes


def check_input(message: str) -> InputVerdict:
    """Return a refusal verdict when the message tries to break guardrails."""
    for pattern in _INJECTION_RE:
        match = pattern.search(message)
        if match:
            return InputVerdict(
                blocked=True,
                reason=f"input guardrail: matched pattern {pattern.pattern!r}",
            )
    return InputVerdict(blocked=False)


def redact_secrets(text: str) -> tuple[str, int]:
    """Replace key-shaped substrings; returns ``(text, redaction_count)``."""
    count = 0
    for pattern, replacement in SECRET_PATTERNS:
        text, n = re.subn(pattern, replacement, text)
        count += n
    return text, count


def sanitize_output(text: str) -> OutputVerdict:
    """Scrub banned governance wording, redact secrets, bound the length."""
    verdict = OutputVerdict(text=text)
    kept: list[str] = []
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        if any(pattern.search(sentence) for pattern in _GOVERNANCE_RE):
            verdict.removed_sentences.append(sentence)
        else:
            kept.append(sentence)
    cleaned = " ".join(kept).strip() if verdict.removed_sentences else text
    if not cleaned:
        cleaned = (
            "The draft response was removed entirely by output guardrails; "
            "no compliant answer remained. Please rephrase the question."
        )
    cleaned, redactions = redact_secrets(cleaned)
    verdict.redactions = redactions
    if len(cleaned) > MAX_OUTPUT_CHARS:
        cleaned = cleaned[: MAX_OUTPUT_CHARS - 1].rstrip() + "…"
    verdict.text = cleaned
    return verdict


__all__ = [
    "GOVERNANCE_PATTERNS",
    "INJECTION_PATTERNS",
    "InputVerdict",
    "MAX_OUTPUT_CHARS",
    "OutputVerdict",
    "REFUSAL_RESPONSE",
    "check_input",
    "redact_secrets",
    "sanitize_output",
]
