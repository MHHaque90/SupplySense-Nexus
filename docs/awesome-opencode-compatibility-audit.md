# Awesome OpenCode Compatibility Audit

**Audit type:** Inspection-only. No tool was installed, enabled, cloned, or executed. No OpenCode/GSD/Archify/MCP/AGENTS.md/project configuration was modified. No package, lockfile, environment file, database, migration, or git state was touched. This report file is the only artifact created.

**Audit date:** 2026-10-05
**Source:** https://github.com/awesome-opencode/awesome-opencode.git (fetched README, `main` branch)
**Project HEAD:** `d4cba1d1e1520883932d7675caee673eff4d0e0c` (read-only; no git operations performed)

**Evidence tags:** `SOURCE FACT` = stated by the source/list/candidate repo · `INFERENCE` = reasoned from facts · `RECOMMENDATION` = audit advice.

---

## 1. Executive Summary

The Awesome OpenCode list contains **227 entries** (4 official, 136 plugins, 7 themes, 9 agents, 64 projects, 7 resources). Evaluated against SupplySense Nexus's actual workflow (GSD v1.42.3 as the single workflow system, Archify for architecture evidence, Context7/Playwright MCPs, AGENTS.md, no-git-during-development policy):

- **The majority of the list is disqualified by the tool-sprawl policy**: ~40+ planning frameworks, orchestrators, swarms, and multi-agent systems that would duplicate or conflict with GSD.
- **Two candidates provide genuine, currently-unsolved value**: a destructive-command safety net (reinforces the NO COMMIT/NO PUSH policy) and dynamic context pruning (the current stack has zero token-reduction mechanism, while SupplySense routinely generates very large tool outputs).
- **Nothing in the list is needed for Phase 12 frontend work** — the already-configured Playwright MCP covers browser/visual verification; the only dedicated browser plugin in the list is archived.
- The audit brief's MCP list (PostgreSQL, Sequential Thinking, Filesystem) does not match the observed config file on this machine; both facts are reported in §6.

**STATUS: SELECTIVE ADDITIONS RECOMMENDED** — at most 2 additions, user-approval-gated, nothing installed now.

## 2. Audit Scope

- Research: Awesome OpenCode README (full 2,173-line document parsed; all 227 entries cataloged), plus 8 candidate repositories inspected at their own sources (README + GitHub API metadata).
- Analysis: overlap vs GSD/Archify/MCPs/AGENTS.md; token, safety, git, background-agent, Phase 12, maintenance, security, installation, and sprawl criteria per audit brief.
- Out of scope (enforced): any installation, configuration, cloning, execution of candidates, or modification of any project/OpenCode/GSD/Archify/MCP configuration, AGENTS.md, package files, environment files, database, migrations, or git state.
- Honest limitation: **deep inspection covered 8 of 227 entries**; remaining candidates were evaluated from the list's own descriptions (tagged as SOURCE FACT of the list, maintenance status UNKNOWN unless metadata checked).

## 3. Current OpenCode Environment

- `SOURCE FACT`: Config at `C:\Users\mhhaq\.config\opencode\opencode.json` defines MCP servers only — `context7` (remote), `playwright` (local `npx @playwright/mcp@latest`), `github` (remote, `Authorization: Bearer {env:GITHUB_PERSONAL_ACCESS_TOKEN}`).
- `SOURCE FACT`: `opencode.jsonc` contains only permission grants for `~/.config/opencode/get-shit-done/*`.
- `SOURCE FACT`: **No plugins are registered** in either config file (no `plugin` key).
- `SOURCE FACT`: Global dirs: `get-shit-done/`, `agents/` (33 `gsd-*.md`), `command/` (67 `gsd-*` commands, 0 non-GSD), `hooks/` (13 GSD hooks), `skills/` (`hyperframes-registry`, `hyperframes-studio`), `gsd-migration-journal/`.
- `SOURCE FACT`: Session-visible native skills include Archify, hyperframes suite, media-use, brag, customize-opencode — i.e., OpenCode's first-party skills system is in use.
- `SOURCE FACT`: No project-level `opencode.json` exists in SupplySense Nexus.

## 4. Current GSD Environment

- `SOURCE FACT`: GSD **v1.42.3** (`get-shit-done/VERSION`), matching the brief.
- `SOURCE FACT`: 67 commands (`gsd-execute-phase`, `gsd-discuss-phase`, `gsd-code-review`, `gsd-audit-fix`, `gsd-plan-*`, …), 33 subagent definitions (planner, executor, verifiers, reviewers, researchers, auditors…).
- `SOURCE FACT`: 13 hooks on disk: `gsd-validate-commit.sh`, `gsd-prompt-guard.js`, `gsd-read-guard.js`, `gsd-read-injection-scanner.js`, `gsd-workflow-guard.js`, `gsd-context-monitor.js`, `gsd-phase-boundary.sh`, `gsd-session-state.sh`, `gsd-statusline.js`, `gsd-check-update*`, `gsd-update-banner.js`, `gsd-session-state.sh`.
- `INFERENCE`: GSD already covers planning, execution, verification, commit validation, prompt/read guards, injection scanning, workflow gating, phase boundaries, and context monitoring — i.e., the workflow, safety, and context-*observation* layers are occupied.

## 5. Current Archify Environment

- `SOURCE FACT`: Archify skill installed at `C:\Users\mhhaq\.agents\skills\archify\`; used for architecture/workflow/sequence diagrams with repo evidence; its own docs directory contains prior validated deliverables (`docs/architecture-audit/`).
- `INFERENCE`: Architecture visualization and repository-to-diagram evidence are fully covered; any list entry offering "architecture diagrams" or "codebase mapping" duplicates Archify or GSD's `gsd-map-codebase`/`codebase-mapper` agents.

## 6. Current MCP Environment

- **Observed (config file, `SOURCE FACT`)**: context7, playwright, github (PAT-backed).
- **Brief-declared (`SOURCE FACT` of the brief)**: Context7, PostgreSQL, Sequential Thinking, Filesystem.
- **Discrepancy**: PostgreSQL/Sequential Thinking/Filesystem MCPs are **not present** in `~/.config/opencode/opencode.json` on this machine; Playwright and GitHub are present but not mentioned in the brief. `list_mcp_resources` returns empty (no resources exposed). Both statements are reported as-is; the brief may describe another machine or an earlier state. (`INFERENCE`: no config change is attempted either way.)
- `SOURCE FACT`: This audit session has active Context7 doc tools and Playwright browser tools — confirming those two servers run.

## 7. Awesome OpenCode Source Review

- `SOURCE FACT`: README structure: OFFICIAL (4) · PLUGINS (136) · THEMES (7) · AGENTS (9) · PROJECTS (64) · RESOURCES (7) = **227 entries**; section boundaries at lines 49/1324/1404/1497/2092.
- `SOURCE FACT`: Entries are curated one-line descriptions + blockquotes + repo links; the list itself carries no compatibility/testing claims — per-entry facts come from linked repos.
- Deep-inspected (own README + GitHub API): `opencode-dynamic-context-pruning`, `cc-safety-net` (formerly claude-code-safety-net), `envsitter-guard`, `opencode-log-sanitizer`, `opencode-token-tracker`, `opencode-agent-skills`, `opencode-chromium-browser-plugin`, `opencode-semantic-anchors`; metadata-only for `opencode-snip`, `OpenCodeRAG`, `opencode-handoff`, `Opencode-Context-Analysis-Plugin`, `opencode-smart-title`, `opencode-notify`.
- Not inspected individually: orchestrators, planners, auth plugins, notifications, themes, and remaining projects (evaluated from list descriptions only; maintenance UNKNOWN).

## 8. Candidate Categories

Only categories with potential relevance to this environment (full catalog retained in audit notes):

| Cat | Category | Entries in list | Relevance verdict |
|---|---|---|---|
| A | Skills | Agent Skills (JDT), Manage Skills, Openskills, Command Inject, opencode-skills | All duplicate OpenCode's native skills system → none needed |
| B | Plugins | 136 | 2 shortlisted (§24), rest filtered |
| C | Agents | 9 agent collections | Overlap GSD's 33 agents → none needed |
| D | Agent orchestration | ~40 (FlowDeck, arise, Workspace, Ensemble, Mission Control, Swarm, CrewBee, Oh-My-Opencode, hiai, …) | **High-threshold class → all rejected** |
| E | Context/token optimization | DCP, Magic Context, snip, trackers (~12), memory plugins (~10) | 1 shortlisted, 1 deferred |
| F | Safety/security | cc-safety-net, Envsitter, Semantic Anchors, Log Sanitizer, sandboxes (bx/jailoc/brood-box/Deck/Cupcake) | 1 shortlisted; sandboxes unusable (no Docker; bx=macOS) |
| G | Git tooling | Worktree, Mission Control, PR Auto-Signature, GitHub Release, Pilot, Actions | **All risky under NO-COMMIT policy → rejected** |
| H | MCP integrations | ~20 MCP-bundling entries | Duplicates of existing MCPs → none needed |
| I | Testing | eval-harness, Swarm test agents, FlowDeck TDD | GSD + pytest cover → none needed |
| J | Documentation | OpenSpec, Chat Export, Xberg, HTML→MD | Archify + GSD docs commands cover → none needed |
| K | Architecture | OpenSpec, Tree-sitter Pack, OpenCodeRAG | Archify/GSD-map cover → none needed (RAG deferred) |
| L | UI/frontend | Chromium plugin (archived), TypeUI, Unship | Playwright MCP already covers → none needed |
| M | Background agents | Background Agents, Pocket Universe, Pocket/async cluster | High-threshold → rejected (§15) |
| N | Productivity | notify*, TTS, quotes, titles, canvas, visualizer | Cosmetic → none needed |
| O | Themes | 7 | Neutral, no workflow value → not recommended |
| P | Other | auth plugins, proxies, mobile/web clients | Irrelevant or trust-questionable → none needed |

## 9. GSD Compatibility

| Candidate (serious) | Classification | Rationale |
|---|---|---|
| cc-safety-net | **GSD-COMPLEMENTARY △** | Different layer: pre-execution blocking of destructive git/fs/secret commands vs GSD's commit-time validation & read-guards; must verify the two hook systems don't suppress each other at install |
| Dynamic Context Pruning | **GSD-COMPATIBLE ✓** | Operates on conversation context; adds `/dcp` commands only (no name collisions with 67 `gsd-*` commands); no agents, no lifecycle hooks touching GSD phases |
| opencode-snip | **GSD-COMPATIBLE ✓** (deferred) | Shell-output reduction; requires command-prefix habit → would need an AGENTS.md note (out of audit scope) |
| Token trackers (cluster) | GSD-OVERLAPPING △ | `gsd-context-monitor.js` already observes context; trackers add display only |
| FlowDeck / BMAD / GoopSpec / Roadmap / Plan Manager / BRHP / Micode / OpenSpec / ForLoop / Swarm / CrewBee / oh-my-opencode / hiai / Ensemble / Mission Control / arise / Open Dynamic Workflows / Subtask2 / OrgX / Pilot / Ralph Wiggum / Gem Team / NERV / Agentic | **GSD-CONFLICTING ✗** | Each is another planning framework, task manager, orchestrator, or multi-agent system: adds commands/agents/hooks, competing lifecycle, duplicated context |
| Memory plugins (Honcho, mnemoria, lemma, opencode-mem, Harness Memory, Magic Context, claude-memory, short-term-memory, simple-memory) | GSD-OVERLAPPING ✗ | Duplicate GSD session-state/AGENTS.md knowledge persistence via injected context |
| Git automation (Worktree, Mission Control, PR Auto-Signature, GitHub Release, handoff-p2p, Worktree Memory Sync, Pilot) | GSD-CONFLICTING ✗ + policy risk | Competing git automation on top of a no-git policy |

## 10. Archify Compatibility

- **No recommended candidate duplicates architecture visualization or repository analysis** — the only adjacent entries (OpenSpec, Tree-sitter Language Pack, OpenCodeRAG, SwarmVault, gitingest-in-Froggy) either duplicate Archify/GSD-mapping or were deferred (§25).
- `SOURCE FACT`: The two recommended tools do not generate diagrams, do not analyze architecture, and introduce no competing architecture workflow → **both Archify-compatible (✓)**.

## 11. MCP Compatibility

- **No MCP addition is recommended.** Every MCP-relevant list entry was checked against the running set:
  - hiai and FlowDeck **bundle Context7** (duplicate of existing server) plus 6–9 more servers → large context cost, rejected.
  - RedCode's bundled Browser MCP duplicates the existing Playwright MCP.
  - Ejentum's reasoning tools duplicate the (brief-declared) Sequential Thinking capability.
  - Memory MCPs (Lemma/With Context/Vestige/supamem/Hipocampo) duplicate GSD state + Filesystem capability and add injection overhead.
  - Unique-but-unneeded: RunAPI (model pricing), Xquik (Twitter), AgentDeals (vendor deals), Crawlberg (crawling — webfetch exists).
- `INFERENCE`: net new MCP count for this environment should remain **zero**.

## 12. Token/Context Analysis

**HIGH BENEFIT**
- **Dynamic Context Pruning** (`SOURCE FACT`: prunes obsolete tool outputs, dedups tool calls, purges errored tool inputs via a `compress` tool; session history preserved with placeholders). Directly targets this project's largest token sink: full pytest runs (768 tests, ~13.5 min output), ruff/pytest verbose logs, big file reads. `SOURCE FACT` caveats: rewrites content sent to the LLM, prompt-cache invalidation cost, `autoUpdate: true` default, dev slowed (successor `sleev`).

**MEDIUM BENEFIT**
- **opencode-snip** (`SOURCE FACT`: claims 60–90% token cut on shell output by `snip` prefixing) — deferred because adoption requires workflow/AGENTS instruction changes.

**LOW / NEUTRAL** (measurement, not reduction)
- Token tracker cluster (Context Analysis, Token Tracker, Tokenscope, Token Monitor, Quota, Throughput, Telemetry, OpenTab, Tokscale, agenttrace). GSD's context-monitor already observes context. Recommendation: at most one, later, if budgets become a measured pain point.

**NEGATIVE** (increase token usage)
- Orchestrators/agents (each adds system prompts, agent catalogs, tool descriptions: FlowDeck's 25 agents + 24 skills + 17 commands; hiai's 10 visible agents + bundled MCP wiring).
- Memory plugins (continuous injection; Harness Memory claims −73% vs CLAUDE.md but replaces AGENTS.md patterns already in use).
- Semantic Anchors, Workaholic, Hooks-plugin stylesteppers (per-message overhead).

## 13. Safety Analysis

- **Existing safety stack (`SOURCE FACT`)**: GSD hooks — prompt-guard, read-guard, injection-scanner, workflow-guard, validate-commit; OpenCode native permission blocks (`opencode.jsonc`); AGENTS.md security rules.
- **cc-safety-net** (`SOURCE FACT` from its repo): pre-execution parser blocks destructive git/shell commands and secret-file access (SSH keys, `.env`, `~/.aws`) across 14 CLIs incl. OpenCode; `npx cc-safety-net install` writes per-CLI hooks + `.cc-safety-net/` policy dir; MIT; **fail-open by design**; explicitly "not a sandbox"; local-only, no stated telemetry.
- `RECOMMENDATION`: this is the single list entry that directly reinforces the NO COMMIT / NO PUSH / NO GITHUB-WRITE policy at the command layer — **complementary △** to GSD (different enforcement moment), conditional on install-time hook-conflict verification.
- Rejected for safety: Envsitter Guard (**STALE**, last push 2026-01-15; no `.env` exists today); Log Sanitizer (5 stars — trust too low for prompt-rewriting code); Semantic Anchors (6 stars; agent can call its own `anchor-bypass` — enforcement defeatable); bx/jailoc/brood-box/Deck/Cupcake (Docker unavailable on this machine; bx is macOS-only).

## 14. Git Safety Analysis

| Candidate | Verdict | Reason |
|---|---|---|
| cc-safety-net | **CONDITIONALLY SAFE** | Its purpose is blocking destructive git (`reset`, `clean`, `push`, …); install writes hook config (approve once); fail-open means no lockout risk |
| Dynamic Context Pruning | **SAFE** | No git interaction (stated) |
| opencode-snip / trackers / themes / notify-style | SAFE (but mostly rejected on merit) | No git ops |
| Opencode Worktree / Worktree Memory Sync | **RISKY** | Creates/switches worktrees — git state changes |
| OpenCode Mission Control | **INCOMPATIBLE** | Merge trains, PRs, automatic rollback |
| PR Auto-Signature | **INCOMPATIBLE** | Writes to commits/PRs/issues |
| GitHub Release | **INCOMPATIBLE** | Tags + publishes releases |
| Pilot | **INCOMPATIBLE** | Daemon polling GitHub issues |
| opencode-handoff-p2p | **INCOMPATIBLE** | Pushes session data to GitHub repos |
| GoopSpec | **RISKY** | "Wave execution with atomic commits" (auto-commit design) |
| opencode-review | **RISKY** | Operates on *staged* changes + auto-fix chain (assumes a staging workflow the policy forbids) |

- `SOURCE FACT` (existing stack, not from the list): the configured **GitHub MCP is PAT-backed and write-capable**; under the no-GitHub-write policy its use must remain read-only by operator discipline. Flagged as an existing trust surface, unchanged by this audit.

## 15. Background Agent Analysis

High bar applied per brief. Rejected as a class: Background Agents, arise, Opencode Workspace, Ensemble, Mission Control, Pocket Universe, Open Dynamic Workflows, CrewBee, oh-my-opencode (+Slim), hiai, Swarm/SwarmClaw/Swarm Plugin, Open Conclave, Micode, Subtask2.

- `INFERENCE`: GSD's 33 subagents already provide structured delegation inside the deterministic lifecycle; every listed alternative adds a second orchestrator, extra system prompts, tmux/worktree machinery, or uncontrolled parallel edits — exactly the "unnecessary orchestration layer" and "uncontrolled modifications" the project rules forbid.
- Background *process* utility (server managers, notify daemons) is orthogonal and archived where relevant (`opencode-notify` = **ARCHIVED**). **No background-agent recommendation.**

## 16. Frontend / Phase 12 Relevance

- `SOURCE FACT`: **Playwright MCP is already configured and active** (`@playwright/mcp` in `opencode.json`; browser tools available this session) → visual verification, DOM inspection, screenshots, and E2E capability for Phase 12 already exist. **No addition needed.**
- Chromium browser plugin: `SOURCE FACT` — source repo **ARCHIVED**, successor package `opencode-chromium` exists but auto-rewrites harness configs, adds native-messaging host + background runtime + optional cloud calls → rejected as duplicate-of-Playwright with deeper trust surface.
- TypeUI (design skills) and Unship (UI variant comparison): list-description only, uninspected → not recommended (cannot claim capability without source).
- `RECOMMENDATION`: Phase 12 should start with the existing toolchain; reassess only if a concrete accessibility/E2E gap appears after the readiness gate lifts.

## 17. Architecture/Documentation Relevance

- Archify (diagrams) + GSD (`gsd-map-codebase`, `gsd-docs-update`, codebase-mapper/doc-writer agents) + Context7 (library docs) cover architecture and documentation.
- Duplicates rejected: OpenSpec, SwarmVault, Froggy/gitingest, Tree-sitter Language Pack, Chat Export. Deferred only: OpenCodeRAG (§25) — retrieval rather than re-reading, but unproven need at ~174 porcelain files.

## 18. Testing Relevance

- Current coverage (`SOURCE FACT`): pytest 768 tests + coverage target, ruff, GSD test/review/verifier agents, `gsd-add-tests`, `gsd-nyquist-auditor`.
- List candidates: eval-harness (skill regression with **pre-push hook** + GitHub Action — git-triggered, no CI on this machine → rejected); Swarm/FlowDeck "test agents" (orchestrator duplicates → rejected); ForLoop (cloud autopilot → rejected).
- `RECOMMENDATION`: no testing-tool additions; Phase 12 UI testing uses the existing Playwright MCP.

## 19. Maintenance Analysis

| Candidate | Classification | Evidence (GitHub API) |
|---|---|---|
| Dynamic Context Pruning | **HEALTHY** | 4,318★, pushed 2026-09-25, not archived, AGPL-3.0; dev slowed (successor announced) |
| cc-safety-net | **HEALTHY** | 1,581★, pushed 2026-10-07, MIT, 11 open issues |
| opencode-snip | ACTIVE | 147★, pushed 2026-10-01, MIT |
| OpenCodeRAG | ACTIVE | 56★, pushed 2026-10-07, MIT (metadata only) |
| opencode-handoff | MAINTAINED BUT SMALL | 175★, pushed 2026-08-26, MIT |
| opencode-token-tracker | MAINTAINED BUT SMALL | 11★, pushed 2026-04-14; README MIT vs API license null (discrepancy) |
| semantic-anchors | MAINTAINED BUT SMALL | 6★, pushed 2026-06-06, Apache-2.0 |
| envsitter-guard | **STALE** | 81★, pushed 2026-01-15 (~8.5 months) |
| Context Analysis | **STALE** | 189★, pushed 2025-10-28 (~12 months) |
| opencode-agent-skills | **STALE by intent** | README: maintenance mode, "no longer necessary" (native skills exist) |
| chromium-browser-plugin | **ARCHIVED** | repo archived, redirect to successor |
| opencode-notify | **ARCHIVED** | archived: true |
| Orchestrators/planners (FlowDeck, BMAD, hiai, …) | UNKNOWN | not individually inspected → cannot recommend uninspected core-workflow tools |

## 20. Security/Privacy Analysis

- **cc-safety-net**: permission scope = hook over every command/file-tool call; local-only, no stated network/telemetry; fail-open (availability-safe, security-soft); MIT; 1.5k★ → **trust level acceptable with the noted fail-open limitation**.
- **Dynamic Context Pruning**: rewrites prompt content pre-LLM (integrity consideration); npm auto-update by default (**supply-chain surface — pin version at install**); AGPL-3.0 (license attaches to the plugin code, not this project — `INFERENCE`; no redistribution planned); local debug logs under `~/.config/opencode/logs/dcp/`.
- Rejected on security grounds: auth-freeloading plugins (Antigravity/Gemini/Codex auth wrappers — credential and ToS risk, irrelevant here); Log Sanitizer (prompt-rewriting with 5★ trust and a deliberate `<no-redact>` bypass); handoff-p2p (session exfiltration to GitHub repos); token-tracker curl-install (trust-on-first-use file drop).
- `SOURCE FACT`: nothing in the recommended set accesses the SupplySense database, `.env`, or GitHub credentials.

## 21. Installation Complexity

(Commands listed for future reference only — **not executed**.)

| Candidate | Documented install | Config change | Restart | Extra deps | Installs hooks/commands/agents |
|---|---|---|---|---|---|
| cc-safety-net | `npx -y cc-safety-net@latest install` (+ `gui`, `doctor`) | Writes per-CLI hook config + `.cc-safety-net/` policy dir | Yes (CLI restart) | Node 18+, npx package | **Hooks: yes**; no agents/commands |
| Dynamic Context Pruning | `opencode plugin add @tarquinen/opencode-dcp@latest` (README states it adds itself to **global** config) | Adds plugin entry to global `opencode.json`; creates `~/.config/opencode/dcp.jsonc` | Yes | npm/Bun plugin, auto-updates on by default | **Commands: `/dcp`, `/dcp-compress` + `compress` tool**; no agents |
| opencode-snip (deferred) | not deep-inspected | unknown | unknown | unknown | unknown |

## 22. Global vs Local Recommendation

- **cc-safety-net → GLOBAL**: broadly applicable, stable safety tooling across all projects (principle: global for broadly useful safety).
- **Dynamic Context Pruning → GLOBAL**: token waste is project-independent; the plugin is per-session context machinery, not project workflow.
- Everything else in the shortlists → **NOT RECOMMENDED** or **SKILL-ONLY/MCP-ONLY = none applicable** (no skill or MCP additions proposed).
- Explicitly not global: no orchestrator, planner, or task-manager may be installed at any scope (tool-sprawl policy).

## 23. Candidate Compatibility Matrix

| Candidate | Category | GSD | Archify | MCPs | Token Impact | Safety | Phase 12 | Overall |
|---|---|---|---|---|---|---|---|---|
| cc-safety-net | F Safety | △ | — | — | NEUTRAL | **+strong** | — | **RECOMMEND (conditional)** |
| Dynamic Context Pruning | E Context | ✓ | ✓ | — | **HIGH BENEFIT** | — | ✓ (smaller contexts during UI work) | **RECOMMEND (conditional)** |
| opencode-snip | E Context | ✓ | ✓ | — | HIGH (claimed) | — | ✓ | CONSIDER LATER |
| OpenCodeRAG | K Indexing | ✓ | △ | — | MEDIUM? (unproven) | — | — | CONSIDER LATER |
| opencode-handoff | N Productivity | △ | — | — | NEUTRAL | — | — | CONSIDER LATER |
| Token tracker (one of cluster) | E Observability | △ | — | — | NEUTRAL | — | — | CONSIDER LATER |
| envsitter-guard | F Safety | ✓ | — | — | NEUTRAL | +small | — | CONSIDER LATER (stale) |
| Any orchestrator/swarm/parallel-agent (FlowDeck, arise, Workspace, Ensemble, Mission Control, Swarm, CrewBee, oh-my-opencode, hiai, …) | D Orchestration | ✗ | ✗ | ✗ (bundles Context7) | NEGATIVE | ✗ (uncontrolled edits) | ✗ | **DO NOT INSTALL** |
| Any second planning framework (BMAD, GoopSpec, Roadmap, Plan Manager, BRHP, Micode, OpenSpec, ForLoop, Pilot, Gem Team, NERV, …) | D Planning | ✗ | ✗ | — | NEGATIVE | — | ✗ | **DO NOT INSTALL** |
| Git automation (Worktree, PR Auto-Signature, GitHub Release, handoff-p2p, Worktree Memory Sync) | G Git | ✗ | — | — | NEUTRAL | **✗ policy risk** | — | **DO NOT INSTALL** |
| Memory plugins (Honcho, mnemoria, lemma, mem, Harness Memory, Magic Context, …) | E Memory | ✗ | — | ✗ | NEGATIVE | — (cloud variants) | — | **DO NOT INSTALL** |
| opencode-agent-skills | A Skills | △ | — | — | NEUTRAL | — | — | **DO NOT INSTALL** (native skills supersede) |
| chromium-browser-plugin | L Browser | ✓ | — | ✗ (dupes Playwright) | NEUTRAL | △ | ✗ dup | **DO NOT INSTALL** (archived) |
| semantic-anchors / log-sanitizer | F Safety | ✗ (dupes GSD guards) | — | — | NEGATIVE | △ self-bypass / low trust | — | **DO NOT INSTALL** |
| Themes (7) / notifications / TTS / quotes / visualizer / cosmetics | N/O | ✓ | — | — | NEUTRAL | — | — | not needed |

## 24. Recommended Now

**Max 5; only 2 survive the "Do we actually need it?" test (§25/§27).**

1. **cc-safety-net** — `https://github.com/kenryu42/cc-safety-net` (list entry "CC Safety Net", Safety/Git category).
   - `RECOMMENDATION`: install **global**, after user approval, with a GSD-hook conflict check (`gsd-validate-commit`/`gsd-read-guard` must still fire afterwards; `uninstall` documented if not).
   - Why now: it is the only maintained, OpenCode-explicit, MIT-licensed layer that blocks `git push`/destructive git/secret reads **before execution** — exactly the policy the project must uphold; GSD validates commits but does not (per observed hook names) pre-block arbitrary destructive commands.
2. **Dynamic Context Pruning** — `https://github.com/Tarquinen/opencode-dynamic-context-pruning` (Context/token category).
   - `RECOMMENDATION`: install **global** with **version pinning and autoUpdate disabled** (supply-chain hygiene), after user approval; first validation = confirm GSD statusline/context-monitor still behave and that pytest/ruff mega-outputs get pruned as expected.

Both are phase-independent (help during Phase 12 as well), GSD-compatible, Archify-compatible, MCP-neutral.

## 25. Consider Later

Max 5 (none approved now):

1. **opencode-snip** (147★, active) — if shell-output tokens become a measured problem; requires an AGENTS.md instruction (which this audit may not modify) + install-mechanics inspection.
2. **OpenCodeRAG** (56★, active today) — only if repeated codebase exploration shows token waste beyond grep/GSD-mapper capability; needs full security/install review first.
3. **A single token-usage tracker** — if token budgets become a tracked concern; pick an actively maintained one at that time (Context Analysis is stale; token-tracker has license discrepancy).
4. **opencode-handoff** (175★) — only if cross-session continuation proves painful beyond GSD's `gsd-capture`/session-state.
5. **Envsitter Guard** — re-evaluate **if and when** a real `.env` with `OPENAI_API_KEY` exists; currently STALE (8.5 months) and no `.env` file exists → verify freshness or find replacement first.

## 26. Do Not Install

Representative, with reasons (list descriptions = SOURCE FACT of the list):

- **FlowDeck, @bluelovers/opencode-arise, Opencode Workspace, OpenCode Ensemble, OpenCode Mission Control, OpenCode Swarm, CrewBee, Oh My Opencode (+Slim), hiai-opencode, Open Dynamic Workflows, Pocket Universe, Open Conclave, Swarm Plugin/SwarmClaw** — second orchestrators/multi-agent systems: duplicate GSD execution, negative token impact, uncontrolled parallel modifications, some bundle duplicate MCPs (Context7). `UNKNOWN` maintenance (uninspected) → cannot recommend core-workflow tooling on description alone anyway.
- **opencode-bmad-workflow, GoopSpec, Opencode Roadmap, OpenCode Plan Manager, BRHP, Micode, OpenSpec, ForLoop Planner, Pilot, OrgX, Ralph Wiggum, Gem Team, NERV, Agentic, opencode-kanban, Vibe Kanban, Beads** — competing planning/task frameworks or auto-commit designs; violate "ONE workflow system".
- **Opencode Worktree, PR Auto-Signature, GitHub Release, Worktree Memory Sync, opencode-handoff-p2p, opencode-review** — git-state or GitHub automation under a NO-COMMIT/NO-PUSH policy; RISKY/INCOMPATIBLE (§14).
- **Honcho, oc-mnemoria, Lemma, Opencode Mem, Harness Memory, Magic Context, OpenCode Claude Memory, opencode-short-term-memory, Simple Memory, Akephalos** — memory layers duplicating AGENTS.md + GSD session state via constant context injection; some are cloud-backed (privacy).
- **opencode-agent-skills** — self-declared obsolete against native skills (`SOURCE FACT`: README maintenance mode).
- **opencode-chromium-browser-plugin** — ARCHIVED source; duplicates active Playwright MCP; deep config-rewriting install.
- **envsitter-guard (now), opencode-log-sanitizer, semantic-anchors** — STALE / 5★ prompt-rewriting / 6★ self-bypassable respectively.
- **bx, jailoc, brood-box, Deck, Cupcake, Agent of Empires** — sandboxing requiring Docker/macOS; Docker unavailable on this machine.
- **Auth wrappers (Antigravity, Gemini Auth, Codex Auth, Kilo/Omniroute, LiteLLM, CCS sync, provider-alias…)** — irrelevant and credential-trust risk.
- **Notifications/TTS/quotes/visualizer/personality/ascii/unmoji/warthcraft/WakaTime/Canvas** — no workflow value.
- **All 7 themes** — harmless but unnecessary; not recommended (neutral).
- **Agents section (Claude Subagents, deliberation, Python Expert, Redstone, server-manager…)** — duplicate GSD's agent roster; uninspected.

## 27. Top 3 Recommendations

**Only two candidates genuinely pass the evidence bar — deliberately not forcing a third.**

### 1. cc-safety-net
- **Repository:** https://github.com/kenryu42/cc-safety-net (listed as "CC Safety Net")
- **Category:** Safety/security (F) + Git safety (G)
- **What it does:** Pre-execution guard parsing agent commands/file reads; blocks destructive git/shell commands and secret access (SSH keys, `.env`, `~/.aws`) before they run; supports OpenCode among 14 CLIs. (`SOURCE FACT`)
- **Why it helps:** Enforces the NO COMMIT / NO PUSH / NO GITHUB-WRITE policy at the command layer — the strongest safety improvement available in the list.
- **vs GSD:** GSD-COMPLEMENTARY — GSD validates commits and guards reads/prompts; this blocks destructive commands pre-execution. Install-time hook-conflict check required (△).
- **vs Archify:** No overlap (✓).
- **Token impact:** NEUTRAL (local hook; short block messages).
- **Security impact:** Positive (blocks secret reads + destructive ops); limitation: fail-open, not a sandbox.
- **Maintenance:** HEALTHY — 1,581★, pushed 2026-10-07, MIT.
- **Scope:** GLOBAL. **Complexity:** Low (`npx … install`, restart, `doctor` to verify). **Risk:** Low-medium (writes hook config; fail-open; verify GSD hooks post-install).

### 2. Dynamic Context Pruning
- **Repository:** https://github.com/Tarquinen/opencode-dynamic-context-pruning
- **Category:** Context/token optimization (E)
- **What it does:** Prunes obsolete tool outputs, dedups tool calls, purges errored tool inputs; optional model-triggered `compress`; history kept with placeholders. (`SOURCE FACT`)
- **Why it helps:** The stack has zero token-reduction mechanism while this project generates very large tool outputs (768-test pytest runs, verbose lint) — the strongest token/context improvement identified.
- **vs GSD:** GSD-COMPATIBLE — no lifecycle/agent/phase overlap; adds only `/dcp` commands (✓).
- **vs Archify:** No overlap (✓).
- **Token impact:** HIGH BENEFIT (its entire purpose; caveat: prompt-cache invalidation cost stated by source).
- **Security impact:** Neutral-to-watch: rewrites prompt content pre-LLM; npm auto-update default → pin version; AGPL-3.0 applies to plugin code.
- **Maintenance:** HEALTHY — 4,318★, pushed 2026-09-25 (dev slowed; successor announced).
- **Scope:** GLOBAL. **Complexity:** Medium (`opencode plugin add …`, writes global config + `dcp.jsonc`, restart). **Risk:** Medium (context manipulation correctness must be validated against GSD statusline/monitor).

**Third slot: intentionally empty.** No other candidate clears maintenance + compatibility + genuine-need simultaneously (snip is next-in-line but deferred to §25).

## 28. Tool-Sprawl Assessment

- Workflow systems: **1 (GSD)** → unchanged. Architecture systems: **1 (Archify)** → unchanged. MCPs: **unchanged (no additions)**. Skills: native + hyperframes/Archify → unchanged. Plugins: **0 today → ≤2** if both recommendations approved.
- The list's ~40 orchestration/planning entries were rejected precisely to preserve this shape; every "consider later" item is individually gated and would still leave one workflow system intact.
- **Verdict: sprawl risk effectively zero under this recommendation set.**

## 29. Final Recommendation

Adopt **at most two additions**, both global, both conditional on user approval and a post-install verification pass (GSD hooks still firing; `/dcp` behavior sane; `cc-safety-net doctor` clean):

1. `cc-safety-net` — safety reinforcement (strongest safety improvement).
2. `opencode-dynamic-context-pruning` — token reduction (strongest token improvement), version-pinned, auto-update disabled.

Do **not** adopt any orchestrator, planner, memory layer, git automation, MCP, skill loader, browser tool, or theme. Re-run a focused re-assessment for frontend-specific needs only after the Phase 12 readiness gate resolves (Phase 12 audit found the existing Playwright MCP already sufficient). Nothing is installed by this audit; the user decides.

## 30. Exact Next Step

1. User reviews §24–§27 and approves/rejects each of the two candidates independently.
2. If approved, run (manually, outside any development phase; these are the exact documented commands — **not executed during this audit**):
   - `npx -y cc-safety-net@latest install` → then `npx cc-safety-net doctor` → then verify GSD hooks (`gsd-validate-commit`, `gsd-read-guard`) still fire with a harmless probe.
   - `opencode plugin add @tarquinen/opencode-dcp@latest` → then edit the plugin entry/config to **pin the version and disable `autoUpdate`** → restart OpenCode → verify `/dcp` exists and GSD statusline still renders.
3. Re-check `git rev-parse HEAD` (must remain `d4cba1d…`) and `git status --porcelain` (174 lines, report file only) after any future install session.
4. If either verification fails: uninstall immediately (`npx cc-safety-net uninstall` / remove plugin entry) and revert to the current stack unchanged.
5. Reassess §25 items only when their triggering conditions occur (a real `.env`, measured token pressure, Phase 12 gate resolution).

**STATUS: SELECTIVE ADDITIONS RECOMMENDED**
