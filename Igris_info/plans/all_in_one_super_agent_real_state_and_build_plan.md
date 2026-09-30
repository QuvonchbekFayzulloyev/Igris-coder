# IGRIS All-in-One Super Agent

## Real-State Audit and Remediation Plan

**Date:** 2026-09-30  
**Scope:** `Igris_info/`, `Igris_brain/`, `Igris_Interface/`, `Igris_Memory/`  
**Evidence basis:** source inspection, runtime entry-point inspection, targeted tests, and manifest path checks. No composite quality percentage is assigned because the repository does not currently produce a reproducible whole-system score.

## 1. Executive Verdict

IGRIS is a substantial local-agent platform, but it is not yet a real all-in-one super agent. The individual capabilities are present in useful form: deterministic routing, LLM tool calls, workspace tools, MCP integration, memory, safety filters, verification, checkpoints, a task supervisor, web strategy, drawing assurance, and a React/Tauri interface.

The missing quality is integration discipline. Several components can independently claim ownership of planning, execution, clarification, streaming, completion, and memory. The documentation also reports a newer and cleaner system than the runtime actually exposes. The result is a capable collection of subsystems rather than one consistent agent contract.

### Evidence of documentation drift

- `Igris_info/protocol_manifest.json` was last updated on 2026-09-13.
- The manifest contains 14 protocol records; 12 contain at least one literal file path that does not resolve in the current workspace. Examples include `Igris_brain/igris_agent.py`, `Igris_brain/executor.py`, `Igris_brain/task_supervisor.py`, and `Igris_brain/safety.py`, while the current code is under `agent/`, `executor/`, `task/`, and `safety/` subpackages.
- `Igris_info/docs/architecture_overview.md` says `Roadmap v4 Status: 100% Complete`, but it also describes stale paths, obsolete component counts, and a different runtime topology.
- `Igris_info/README.md` reports approximately 92% health and 160+ regression tests without a reproducible calculation. The current repository contains 61 `tests/test_*.py` files, while the full suite previously reached 88% and then stopped producing output; focused suites pass, but whole-suite completion is not proven.

These are documentation and verification failures, not merely formatting problems. They prevent future agents from knowing which claims are safe to trust.

## 2. Current Runtime Ownership

| Responsibility | Current owners | Real status | Required owner |
|---|---|---|---|
| Public chat routing | `server.server`, `IgrisAgent.chat`, `IgrisAgent.chat_stream` | Mostly working, recently unified for streaming | `IgrisAgent` facade |
| Intent and pipeline selection | `request_classifier.py`, `PIPELINE_SPECS`, requirement extractor | Duplicated concepts; specs are partly descriptive | `RequestRouter` + typed `RunPlan` |
| Planning | `TaskPlanner`, `LLMDAGPlanner`, composition engine, legacy layered planner | Multiple plan formats | `Planner` interface with one normalized output |
| Single-task execution | `AgentExecutor.run`, `AgentExecutor.run_native`, chat tool loop | Three paths with different evidence behavior | `AgentExecutor` |
| Multi-task orchestration | `TaskSupervisor`, previously duplicated streaming supervisor | Improved, but the contract is not shared by all APIs | `TaskSupervisor` |
| Layered streaming | `LayeredAgent` compatibility code and standard `IgrisAgent.chat_stream` | Compatibility code still contains a separate execution model | Event adapter only; no second executor |
| Clarification | `IgrisAgent._clarification_gate`, `LayeredAgent.ClarificationManager`, `/api/chat/clarify` | Two session protocols | One `ClarificationService` |
| Verification | executor gates, world state, SVG/web checks, action evidence | Strong pieces, not universal across all entrypoints | `VerificationService` |
| Final response | `IgrisAgent`, `ResponseGenerator`, layered synthesis, frontend formatting | Several completion formats | One response/completion contract |
| Memory | `MemoryBridge`, CAG, MAG, `Igris_Memory` runtime/persistent stores | Functional but polluted by repeated and stale records | One write gate plus maintenance/quarantine |
| UI task status | backend RunManager plus frontend auto-mode/local task queue plus Tauri fallback | Can display or create success without backend evidence | Backend-owned run state |

## 3. Blocking Gaps

### P0: false success and split runtime contracts

1. Every public execution entrypoint does not share the same completion/evidence contract. `/api/chat`, `/api/chat/stream`, `/api/agent/run`, `/api/agent/toolrun`, frontend auto-mode, and the Tauri command path do not all prove the same thing before reporting success.
2. The Tauri command `send_chat_message` still returns text such as `Backend would process: ...` or `Local response: ...`; this is a mock response, not an agent execution result.
3. Frontend auto-mode marks a queued task `completed` after `agentTask()` resolves without checking a verified result status or evidence record.
4. The runtime has anti-hallucination modules, but they are not the single mandatory gate for every response path.

**Exit condition:** no API, UI, CLI, or Tauri path can emit `completed`, `done`, or equivalent without a typed result containing verification status and evidence.

### P1: multiple orchestration models

1. `IgrisAgent`, `TaskSupervisor`, `AgentExecutor.run`, `AgentExecutor.run_native`, `LayeredAgent`, Smart Build, and Composition each define part of an agent loop.
2. `PIPELINE_SPECS` declares stages and loop shapes, but execution is not driven by a single typed stage contract.
3. `run()` and `run_native()` have different planning and evidence behavior.
4. Layered clarification and core clarification use different session state and resume rules.
5. Frontend event types still include layered events that the production server no longer emits as its canonical path.

**Exit condition:** one normalized `RunRequest -> RunPlan -> ActionRecord -> VerificationRecord -> CompletionRecord` path exists; adapters may translate to SSE, CLI, or UI but may not execute independently.

### P1: memory trust and contamination

`Igris_Memory/brain_data/` contains repeated records, stale answers, and historical false claims such as image creation claims that were not necessarily backed by files. Memory is currently a useful store, but it is not a trusted knowledge base until records carry provenance and verification status.

**Exit condition:** only verified or explicitly marked user-provided facts enter persistent solution memory; old records are quarantined, deduplicated, and never silently treated as ground truth.

### P1: documentation cannot be used as a source of truth

The manifest, protocol files, architecture overview, phase reports, and current code disagree on paths, component ownership, test counts, and completion status. Health percentages are not reproducibly computed.

**Exit condition:** every status claim has a command, timestamp, scope, and raw result; stale paths fail a documentation check.

### P2: incomplete all-in-one capability surface

The platform has core coding, file, web, drawing, UI-build, memory, and browser capabilities, but some are still aspirational or weakly integrated:

- office, diagram, 3D, EDA, audio, and broader artifact validation are not uniformly available;
- voice/STT/TTS is described but not a complete runtime subsystem;
- vision modules exist, but perception-to-action verification is not a single end-to-end contract;
- tool output schemas, permissions, preconditions, postconditions, and timeout policy are not uniformly enforced;
- the complete test suite does not have a proven bounded completion path.

## 4. Requirements

### REQ-AIO-001: Canonical run contract

All entrypoints must normalize to one typed run model containing `run_id`, immutable `goal`, request type, plan, actions, observations, verification records, final status, errors, recovery events, and evidence references.

### REQ-AIO-002: Deterministic state machine

State transitions, retry limits, permissions, cancellation, timeout, completion, and escalation must be deterministic. LLM output may propose a plan or action, but may not directly transition state or mark work complete.

### REQ-AIO-003: Real execution evidence

A success claim requires evidence appropriate to the task: file-on-disk and content checks, command exit status, test result, HTTP/content verification, SVG/artifact validation, or an explicitly recorded human confirmation.

### REQ-AIO-004: One executor boundary

All native tools and MCP tools must pass through one executor boundary with normalized input/output schemas, action IDs, permission checks, timeout, retry policy, and postconditions.

### REQ-AIO-005: Honest failure semantics

Tool errors, unavailable tools, timeouts, partial work, unknown verification, cancellation, and human escalation must remain visible. Exceptions may not be silently converted to successful results.

### REQ-AIO-006: Multi-task correctness

The supervisor must create a DAG only when the request requires multiple loops, preserve the original goal, execute every node through the canonical executor, and complete a parent only when its required children are verified.

### REQ-AIO-007: Unified clarification

Clarification must use one session service with one session ID, bounded questions, timeout/cancellation, answer history, resume behavior, and a documented API contract.

### REQ-AIO-008: Memory provenance

Every persistent memory record must carry source, run ID, action/evidence references, verification status, model/tool origin, timestamp, and confidence basis. Unverified assistant prose must not become solution memory.

### REQ-AIO-009: Context discipline

Goal, current objective, verified state, relevant memory, and recent history must be ranked under a measured token budget. Irrelevant and conflicting context must be filtered or explicitly flagged.

### REQ-AIO-010: Safety and permissions

Every tool must declare side-effect class, permission policy, timeout, precondition, postcondition, and retryability. Destructive and unsafe actions require confirmation or an explicit policy decision.

### REQ-AIO-011: API/UI truthfulness

Frontend task state, SSE state, CLI state, and Tauri state must be projections of backend run state. Local UI optimism may not create a completed task.

### REQ-AIO-012: Capability registry

All capabilities must be registered with availability, health, input/output schema, safety class, and verification method. Unsupported capability requests must return a truthful `unsupported` result.

### REQ-AIO-013: Observability

Every run must expose structured events for decision, action, result, verification, retry, recovery, cancellation, and final status. Logs must be correlated by `run_id` and `action_id`.

### REQ-AIO-014: Recovery and resume

Cancellation, process restart, tool timeout, and failure must preserve a resumable checkpoint containing goal identity, verified actions, pending work, and current state. Resume must reject mismatched goals.

### REQ-AIO-015: Documentation integrity

Manifest paths, protocol ownership, status, test commands, and architecture diagrams must be generated or checked from the current source tree. No “100% complete” or percentage health claim is allowed without reproducible evidence.

### REQ-AIO-016: Bounded quality gate

Unit, integration, API, UI-contract, safety, and scenario tests must complete within explicit timeouts. A hanging full suite is a failed quality gate, not a pass.

## 5. Build Rules

1. **One owner per responsibility.** A compatibility module may translate; it may not reimplement execution.
2. **LLM is advisory.** LLM output is untrusted input to deterministic validators and executors.
3. **No evidence, no success.** “Done”, “created”, “saved”, and “tested” require machine-readable proof.
4. **No silent exception.** Every swallowed exception must become a structured degraded/error event or be justified as an optional capability.
5. **One status vocabulary.** Use `queued`, `running`, `waiting_human`, `partial`, `verified`, `failed`, `cancelled`, `unsupported`, and `stopped`; do not invent per-layer alternatives.
6. **One event envelope.** All adapters use `{run_id, event_id, type, timestamp, status, payload}`.
7. **Goal is immutable.** Replanning can change steps, never the original goal identity or text.
8. **Parent completion is derived.** A supervisor cannot complete while required child work is unverified.
9. **Memory is a consequence of verified work.** Never write raw LLM claims to long-term memory.
10. **Safety before execution.** Validate input, permission, path, policy, and preconditions before invoking a tool.
11. **Postconditions are mandatory for writes.** Read the resulting artifact or inspect the external state after mutation.
12. **Tests must be executable and bounded.** Every claimed fix has a focused test; whole-suite commands have a timeout and report hangs.
13. **Docs contain provenance.** Every factual status line states source path, command, date, and scope.
14. **No fabricated score.** Use `implemented`, `partial`, `missing`, `blocked`, or `unknown` unless a reproducible metric is stored.
15. **Compatibility is temporary.** Every compatibility facade has an owner, deprecation reason, migration target, and removal test.

## 6. Remediation Plan

### Phase 0: Freeze reality and repair the information base

**Goal:** stop building on false documentation.

- Create a generated source manifest from the current tree.
- Replace literal stale paths in `Igris_info/protocol_manifest.json`.
- Mark every protocol `implemented`, `partial`, `missing`, or `unknown` using command evidence.
- Remove unmeasured quality percentages and “Roadmap v4: 100% Complete” claims.
- Add a documentation drift check: every referenced source path must exist; every test claim must include the exact command and result.
- Inventory all public entrypoints and all event/status vocabularies.

**Evidence:** manifest path check passes; docs report the same entrypoints and counts as the source tree.

### Phase 1: Establish the canonical contracts

**Goal:** make fake success structurally difficult.

- Add typed `RunContext`, `RunPlan`, `ActionRecord`, `Observation`, `VerificationRecord`, `ErrorRecord`, and `CompletionRecord`.
- Route `/api/chat`, `/api/chat/stream`, `/api/agent/run`, `/api/agent/toolrun`, CLI, and Tauri through one service facade.
- Make `IgrisAgent` route and prepare context; make `TaskSupervisor` schedule; make `AgentExecutor` execute; make `VerificationService` decide completion.
- Convert all adapters to the one event envelope.

**Evidence:** the same deterministic fixture produces equivalent status, evidence, and completion data through HTTP, SSE, and CLI.

### Phase 2: Consolidate execution and remove duplicate loops

**Goal:** eliminate behavioral divergence.

- Keep `AgentExecutor` as the only real tool executor.
- Keep `TaskSupervisor` as the only multi-loop scheduler.
- Keep `IgrisAgent` as the only public routing facade.
- Convert `LayeredAgent` into an event adapter or remove it after compatibility tests pass.
- Normalize `run()` and `run_native()` behind one executor interface; retain different planning strategies only as internal strategies.
- Remove duplicated streaming supervisor code and obsolete layered event declarations from the frontend after migration.

**Evidence:** no production path directly calls registry/MCP tools outside the executor; search confirms one implementation for each execution responsibility.

### Phase 3: Make verification universal

**Goal:** eliminate remaining false completion.

- Require postconditions for write, patch, delete, rename, artifact, drawing, browser, and command tools.
- Map `Requirement` objects to expected results and `VerificationRecord` methods.
- Make supervisor node completion depend on verification, not returned text.
- Update frontend auto-mode to inspect backend `status` and evidence before setting `completed`.
- Replace Tauri placeholder responses with a real bridge call or an explicit `unsupported/offline` status.

**Evidence:** negative fixtures prove that missing files, wrong content, failed commands, unavailable tools, and fake LLM claims cannot produce success.

### Phase 4: Unify clarification, cancellation, and resume

**Goal:** preserve task identity across human and process boundaries.

- Create one `ClarificationService` and migrate both existing clarification paths.
- Add `waiting_human` to the canonical run state and event contract.
- Store goal ID, completed verified actions, pending actions, and clarification history in checkpoints.
- Test cancellation during every executor strategy and supervisor node.

**Evidence:** a paused run resumes the same run ID and goal; a mismatched checkpoint is rejected; timeout and cancellation never become success.

### Phase 5: Clean and protect memory

**Goal:** turn memory into trusted evidence-backed knowledge.

- Quarantine existing assistant-generated records with no verification metadata.
- Deduplicate by normalized query plus content hash and retain lineage.
- Add conflict resolution by recency, verification status, source authority, and user confirmation.
- Separate `short-turn`, task state, verified solution, user fact, and speculative note schemas.
- Prevent CAG/MAG from returning unverified historical claims as authoritative answers.

**Evidence:** a memory poisoning fixture, contradictory records, and a fake completion record are filtered or explicitly labelled.

### Phase 6: Complete capability and interface contracts

**Goal:** make “all-in-one” truthful and inspectable.

- Register artifact, office, diagram, 3D, EDA, audio, vision, web, code, and voice capabilities with health and verification metadata.
- Implement or explicitly mark STT/TTS and missing domain MCP capabilities as unsupported.
- Align `ChatStreamEvent`, frontend store, CLI, and backend event schema.
- Remove UI status derived from local optimistic assumptions.
- Add capability health endpoint and UI evidence panel sourced from backend run records.

**Evidence:** every advertised capability has a smoke test, a health state, and a truthful unavailable response.

### Phase 7: Quality gate and release

**Goal:** prove the system as a whole.

- Add bounded unit, integration, API, SSE, UI-contract, safety, memory, and scenario suites.
- Run the full suite with a hard timeout and report the exact hanging test if it does not finish.
- Add a small deterministic acceptance matrix: chat, math, weather, file read, file edit, code build, drawing, UI build, web research, multi-task DAG, clarification, cancellation, resume, unsupported capability, and malicious request.
- Generate a release report from test results and source manifest; do not hand-write health percentages.

**Exit criterion:** all P0/P1 requirements pass, no canonical path can fake success, and the full bounded acceptance matrix completes.

### Backend liveness rules

- Watchdog health checks must use a lightweight endpoint and must never restart from stale launch metadata or a single slow request.
- Every automatic restart records failed health checks, process exit code, launch command, and new-process readiness.
- MCP sessions, stdio transports, subprocesses, and event loops must be closed on their owning loop before shutdown.

## 7. Requirement Mapping

| Requirement | Primary phase | Completion evidence |
|---|---|---|
| REQ-AIO-001, 002, 003 | 1-3 | typed run records, state transition tests, verification fixtures |
| REQ-AIO-004, 005, 010 | 2-3 | executor boundary search, tool contract tests, error/permission tests |
| REQ-AIO-006, 007, 014 | 2, 4 | DAG, clarification, cancellation, resume tests |
| REQ-AIO-008, 009 | 5 | memory provenance, conflict, context-budget tests |
| REQ-AIO-011, 013 | 1, 6 | HTTP/SSE/UI/CLI contract tests and correlated events |
| REQ-AIO-012 | 6 | capability registry and smoke-test matrix |
| REQ-AIO-015 | 0, 7 | generated manifest and documentation drift check |
| REQ-AIO-016 | 7 | bounded full-suite report and acceptance matrix |

## 8. Immediate Task List

- [ ] T001 Generate current source manifest and compare every `Igris_info` path.
- [ ] T002 Publish the canonical run/event/status schema.
- [ ] T003 Add a backend integration test proving every public execution endpoint returns evidence-backed completion.
- [ ] T004 Replace frontend auto-mode optimistic completion with backend result status validation.
- [ ] T005 Replace Tauri placeholder chat responses with real bridge results or `unsupported/offline` records.
- [ ] T006 Route all tool execution through `AgentExecutor` and record `run_id`/`action_id`.
- [ ] T007 Migrate clarification to one service and one session contract.
- [ ] T008 Add verification postconditions for all mutating and artifact tools.
- [ ] T009 Quarantine and deduplicate existing unverified memory records.
- [ ] T010 Remove or deprecate `LayeredAgent` execution code after compatibility tests.
- [ ] T011 Align frontend event types with the canonical backend event envelope.
- [ ] T012 Add capability health and unsupported-capability responses.
- [ ] T013 Run the bounded acceptance matrix and diagnose the full-suite hang.
- [ ] T014 Regenerate `protocol_manifest.json`, `README.md`, and architecture docs from verified results.
- [x] T015 Reject stale watchdog launch commands and repair legacy MCP working-directory paths.
- [x] T016 Prevent frontend/backend/Tauri fake success and add backend completion contract regression coverage.
- [ ] T017 Add restart telemetry and a bounded complex-task liveness acceptance test.

## 9. Non-Negotiable Definition of Done

IGRIS may be called an all-in-one super agent only when:

1. one public run contract governs HTTP, SSE, CLI, Tauri, and UI;
2. one executor performs tools and one verifier authorizes completion;
3. every completed action has evidence and every failure remains visible;
4. multi-task, clarification, cancellation, resume, memory, and safety use the same run identity;
5. advertised capabilities have working health checks or are explicitly marked unsupported;
6. documentation is generated from the current code and test evidence;
7. the bounded whole-system acceptance matrix passes without hangs or fabricated success.

## 10. Backend Liveness Incident Rules

When the backend appears to stop during a complex task, diagnose in this order:

1. Check `logs/server.log.err` for an unhandled exception or process exit.
2. Check `logs/watchdog.log` for an automatic restart, reason, and rate-limit state.
3. Check `logs/server_launch.json` and verify the referenced server script exists.
4. Check MCP child-process paths and graceful close errors.
5. Check task status separately from process health: `running`, `queued`, `cancelled`, `partial`, and `error` are not backend death.

The backend is not stable until a complex-task test proves `/api/health` remains reachable, the task reaches a terminal status, MCP children close without cancel-scope errors, no stale restart command is used, and a failed task does not cause process restart.