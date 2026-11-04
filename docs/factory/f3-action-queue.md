# F3 actions and persistent job queue

This note documents the F3 API foundation. The existing browser client has not been migrated to the explicit draft-review flow.

## Action journal

Each project has an append-only `studio/actions.jsonl` event journal. Every record contains a monotonically increasing sequence, the prior event hash, and a SHA-256 hash of its canonical JSON representation. `GET /api/projects/{project_id}/actions` verifies the chain and returns the events and folded action states. A damaged journal fails closed: action and queue operations that need it return a conflict rather than extending or ignoring the damaged history. Secret-bearing keys are omitted and sensitive bearer/token strings are redacted.

## Script proposal flow

1. For an already-v2 project, `POST /api/projects/{project_id}/actions` with `{"kind":"script-draft"}` creates a proposal only. Legacy v1 projects are not migrated by this flow; they must be explicitly migrated first. It records the base revision, model/configuration and generation-parameter fingerprint, privacy scope, and quote expiry. It does not call a provider or change the accepted project.
2. `POST /api/projects/{project_id}/actions/{action_id}/confirm` starts the proposal job. The body must include the proposal's exact `input_fingerprint`, `consent: true`, and `cost_ceiling: {"amount": ..., "currency": "RUB"|"EUR"|"USD"}`. Local jobs also require `privacy_scope: "local"`. A GigaChat job additionally requires `cloud_consent: true`, current cloud acknowledgement in settings, credentials configured locally, an explicit model ID, and a positive ceiling. Quotes expire after ten minutes.
3. Poll `GET /api/projects/{project_id}/actions/{action_id}` or `GET /api/projects/{project_id}/jobs/{job_id}`. When the action is `candidate_ready`, the action response includes `base_spec` and `candidate_spec` for review.
4. `POST /api/projects/{project_id}/actions/{action_id}/apply` with the same input fingerprint accepts the candidate and creates a project revision. `POST .../reject` records rejection without changing accepted state.

The legacy `POST /api/projects/{project_id}/script-draft` route remains present but returns HTTP 409 instead of silently overwriting the accepted script. The web client is intentionally not wired to the new flow in F3.

## Jobs

Jobs are stored as atomic JSON records under `studio/jobs/`; plans are persisted under `studio/plans/`. Canonical states are `queued`, `running`, `completed`, `failed`, and `cancelled`. The existing legacy `GET /jobs?id=...` facade still maps `completed` to `done` and `failed`/`cancelled` to `error`.

- `GET /api/projects/{project_id}/jobs` lists persistent jobs.
- `POST /api/projects/{project_id}/jobs/{job_id}/cancel` cancels queued work or requests cancellation of running work.
- `POST /api/projects/{project_id}/jobs/{job_id}/retry` requires the current input fingerprint and a fresh consent/cost-ceiling confirmation.

The single sequential worker is protected across processes by a filesystem lock. Server startup requeues queued jobs and resumes interrupted ones. Stage outputs use deterministic temporary paths, atomic cache/checkpoint writes, and existing fingerprint-keyed caches so a resumed task can reuse finished units. A GigaChat call with an unknown outcome is not automatically repeated after a crash; it fails safely and requires an explicit retry confirmation to avoid accidental duplicate provider calls.

F3 tests use mocks for provider generation. No real paid provider calls or project migrations are part of this implementation.
