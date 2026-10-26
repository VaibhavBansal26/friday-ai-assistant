# Friday completion audit

Audit date: 2026-07-11. Overall assessed product completion: 65%. This measures verified user-triggered outcomes, not schemas, mock tests, or architecture coverage.

| Area | State | Current evidence | Evidence still required for completion |
|---|---|---|---|
| Tauri desktop shell | Verified unsigned build | Rust 1.97 native compile/tests pass; optimized binary, `Friday.app`, and verified DMG build successfully | Apple signing/notarization, tray, shortcuts, updater |
| Desktop operational UX | Partial | API-backed Home, Tasks, Projects, Ideas, Jobs, Resume, Applications, Email, Calendar, Knowledge, Memory, Content, Video, Learning, Approvals, Audit, Settings; frontend build/tests | Dedicated Coding/GitHub/Websites/Automations views and full browser E2E tests |
| FastAPI gateway | Verified foundation | API routes, security middleware, 171 backend tests | Production process supervision, load tests, authenticated WebSocket E2E |
| Local sessions | Verified foundation | Opaque hashed tokens, expiry/revocation, configured-user bootstrap, desktop bearer/session headers | Enforcement enabled in packaged native build and native E2E verification |
| PostgreSQL | Partial | All 35 tables defined; earlier 17-table live verification | Apply migration 003 and verify all 35 live; RLS; backup/restore test |
| Redis | Partial | Docker service previously returned PONG; event contract exists | Redis Streams adapter, locks/rate limits, reconnect/load tests |
| LangGraph | Verified foundation | All 20 specified nodes compile; agent state, safe plans, and unverified-completion refusal tested | Durable checkpointer, real conditional routing, tool execution E2E |
| Agent boundaries | Verified foundation | All 38 required agents registered and least-privilege tests pass | Domain-agent prompts/evals and end-to-end delegation traces |
| Model router | Partial | Privacy/capability/provider-health routing tested | Live provider health, budgets, model registry, fallback chaos tests |
| OpenAI Responses | Partial | Trusted adapter and mock tests | Explicitly enabled live smoke test, streaming, cost/latency trace |
| Realtime voice | Blocked live | WebRTC/session exchange implemented; microphone path reaches the provider | OpenAI project currently returns `insufficient_quota`; packaged gateway lifecycle, barge-in, wake word |
| ElevenLabs | Blocked | Provider boundary in architecture | Account/API authorization, streaming TTS, pronunciation, fallback tests |
| Credential broker | Partial | Capability scopes, macOS Keychain adapter, atomic OAuth rotation, scope non-expansion tests | Real OAuth grants, provider rotation E2E, reauthentication UI, metadata persistence |
| Tasks | Partial | CRUD, PostgreSQL adapter, audit, desktop UI | Dependencies/subtasks/recurrence/reminders/planning and PostgreSQL UI E2E |
| Projects and ideas | Foundation | Typed services, audit contracts | Persistence, full UI, decision logs, project milestones |
| QMD | Partial | CLI adapter with citation requirements | Install, collection isolation, indexing, embeddings, retrieval evaluation |
| Governed memory | Partial | Proposals, ownership, conflicts, approval, expiry schema | Persistent service, deletion/export UI, poisoning and cross-user E2E |
| GBrain | Experimental boundary | Shadow-only sourced proposals; cannot self-verify | Package evaluation, shadow dataset, quality/security gates, opt-in UI |
| Graphify | Experimental boundary | Read-only edges, source-hash checks, no edit authority | Package integration, repository indexing, measured impact accuracy |
| Job discovery | Partial | Greenhouse adapter, normalization, fingerprints, freshness semantics | Lever/Ashby/Workday/etc., schedulers, dedupe persistence, alerts |
| Job matching | Foundation | Skills/location/salary/authorization scores and hard disqualifiers | Experience/project/education models, candidate profile UI, evaluated precision |
| Resume | Foundation | Source claims, traceable tailoring, metric/technology rejection | Parsing, version persistence, side-by-side UI, PDF/DOCX export and render QA |
| Applications | Foundation | Factual fields, review/blockers, Level 3 preview | Deterministic browser filling, upload/review UI, approved submit and confirmation E2E |
| Browser | Implemented, E2E blocked | Dedicated Chrome-profile Playwright worker, approved-domain policy, preview-only fill, approve-once submission, duplicate protection, CAPTCHA/password/payment blocks, screenshot evidence, and desktop Browser workspace | Live Chrome/form E2E was blocked by the current execution approval/usage limit; persistent external-site auth and redirect/download E2E remain |
| Email | Foundation | Thread-aware drafts/signals and Level 2 preview | Gmail OAuth/API read/draft/send and provider message-ID verification |
| Calendar | Foundation | Proposals, conflicts and Level 2 preview | Google Calendar OAuth/API and provider event-ID verification |
| Coding | Local commits operational | Coding UI inspects the working tree, stages explicit scoped paths, commits, verifies the SHA, and audits evidence; GitHub CLI uses the locally authenticated account | Connect/create a remote, then verify push and PR workflows; secret scanner integrations |
| Device and files | Scoped local actions operational | Friday UI and API can open allowlisted apps, control Music transport, search authorized roots, and preview bounded text; Music launch verified | User folder-picker persistence, broader app adapters, file-write preview/rollback |
| GitHub | Verified evidence foundation | Commit/push/PR/comment/merge evidence rules | GitHub App/API/CLI authentication and approved write E2E |
| CI debugging | Architecture only | Agent capability boundary | Provider log adapters, rerun approval, failure reproduction E2E |
| Website builder | QA foundation | IA, stack, responsive/a11y/build evidence contracts | Scaffolder, component workflow, browser screenshots, preview deploy E2E |
| Content | Local scripting operational | Content Studio composes LinkedIn drafts locally from structured inputs, supports copy/edit review, enforces claim/secret checks, and creates publishing approval previews | LinkedIn OAuth/API publisher, provider post-ID evidence, analytics |
| Video | Local rendering operational | Friday Video Studio can create projects and render evidenced H.264/AAC MP4s with local narration and burned captions; verified 1080×1080 artifact | Rich asset generation, Remotion compositions, ElevenLabs, private YouTube upload |
| Higgsfield | Optional boundary | Provider enum/router; disabled unless configured | API/license/privacy evaluation, account, adapter, quality/cost tests |
| Learning/interviews | Foundation | Active recall, spacing, scoring, feedback-to-topics | Persistent plans/UI, voice interview loop, calibrated evaluation suite |
| Temporal | Contract only | Workflow states, interrupts, retries, compensation tests | Temporal server/worker integration and durable recovery E2E |
| n8n | Contract only | Signed trigger and authority-field rejection | Ten workflows deployed with credential references and gateway callbacks |
| Notifications | Partial | Dedup/redaction/read/dismiss and granted desktop delivery | Native Tauri notifications, preferences UI permission flow, scheduling |
| Observability | Foundation | Redacted traces, cost/tokens, critical release gates | OpenTelemetry/Langfuse exporters, Prometheus/Grafana dashboards, alert tests |
| Security | Strong foundation | Injection, credentials, approvals, idempotency, browser, coding tests | RLS, dependency/SBOM scans, Semgrep/Gitleaks, penetration test, notarized runtime |
| Native release | Partial | Rust compile/tests pass; optimized binary, unsigned `Friday.app`, and checksum-valid 3.2 MB DMG produced | Apple signing/notarization and updater smoke test |

## Current external blockers

1. OpenAI: the configured project currently returns `insufficient_quota`, blocking conversation and model-generated content.
2. GitHub: CLI is installed and authorized, but this workspace has no configured remote repository, so push/PR verification is blocked.
3. Media: FFmpeg and Remotion are not installed; ElevenLabs, Higgsfield, and YouTube are not authorized.
4. Browser: Friday has policy contracts but no packaged browser worker or authorized Chrome-control bridge.
5. Device/files: macOS launch primitives exist, but Friday has no approved folder scopes, media-control adapter, or native execution UI.
6. Accounts: LinkedIn, Gmail, Google Calendar, GitHub, optional Higgsfield, and YouTube are not authorized.
7. Apple release: signing and notarization credentials are unavailable.
8. Docker: installed, but the daemon is unavailable, so migration 003 is not live-verified.

## Definition of 100%

100% requires every row above to be verified or intentionally removed from the approved product scope by the user. Mock tests, schemas, adapters, and architecture documents are not sufficient evidence for live provider, native packaging, or release claims.
