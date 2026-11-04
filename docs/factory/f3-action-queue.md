# F3 actions and persistent job queue

This note documents the F3 API foundation and the F4 browser integration. The browser client now uses the explicit draft-review flow for AI script proposals; existing production-stage job routes remain backward compatible.

## Action journal

Each project has an append-only `studio/actions.jsonl` event journal. Every record contains a monotonically increasing sequence, the prior event hash, and a SHA-256 hash of its canonical JSON representation. `GET /api/projects/{project_id}/actions` verifies the chain and returns the events and folded action states. A damaged journal fails closed: action and queue operations that need it return a conflict rather than extending or ignoring the damaged history. Secret-bearing keys are omitted and sensitive bearer/token strings are redacted.

## Script proposal flow

1. For an already-v2 project, `POST /api/projects/{project_id}/actions` with `{"kind":"script-draft"}` creates a proposal only. Legacy v1 projects are not migrated by this flow; they must be explicitly migrated first. It records the base revision, model/configuration and generation-parameter fingerprint, privacy scope, and quote expiry. It does not call a provider or change the accepted project.
2. `POST /api/projects/{project_id}/actions/{action_id}/confirm` starts the proposal job. The body must include the proposal's exact `input_fingerprint`, `consent: true`, and `cost_ceiling: {"amount": ..., "currency": "RUB"|"EUR"|"USD"}`. Local jobs also require `privacy_scope: "local"`. A GigaChat job additionally requires `cloud_consent: true`, current cloud acknowledgement in settings, credentials configured locally, an explicit model ID, and a positive ceiling. Quotes expire after ten minutes.
3. Poll `GET /api/projects/{project_id}/actions/{action_id}` or `GET /api/projects/{project_id}/jobs/{job_id}`. When the action is `candidate_ready`, the action response includes `base_spec` and `candidate_spec` for review.
4. `POST /api/projects/{project_id}/actions/{action_id}/apply` with the same input fingerprint accepts the candidate and creates a project revision. `POST .../reject` records rejection without changing accepted state.

A proposal is guarded by the exact accepted story content hash plus its original provider/model fingerprint. Metadata-only updates such as navigating to a different studio step do not invalidate an otherwise unchanged candidate; editing the accepted story does. This avoids false stale conflicts while preserving protection against overwriting changed story content. The worker snapshots the accepted story before calling a generator because demo/model adapters may mutate their input; older candidates affected by that bug are reconstructed for review only when the current story still matches the proposal's original hash.

The legacy `POST /api/projects/{project_id}/script-draft` route remains present but returns HTTP 409 instead of silently overwriting the accepted script. F4 wires the web client to the action endpoints; the old direct route is not called by the browser client.

## Jobs

Jobs are stored as atomic JSON records under `studio/jobs/`; plans are persisted under `studio/plans/`. Canonical states are `queued`, `running`, `completed`, `failed`, and `cancelled`. The existing legacy `GET /jobs?id=...` facade still maps `completed` to `done` and `failed`/`cancelled` to `error`.

- `GET /api/projects/{project_id}/jobs` lists persistent jobs.
- `POST /api/projects/{project_id}/jobs/{job_id}/cancel` cancels queued work or requests cancellation of running work.
- `POST /api/projects/{project_id}/jobs/{job_id}/retry` requires the current input fingerprint and a fresh consent/cost-ceiling confirmation.

The single sequential worker is protected across processes by a filesystem lock. Server startup requeues queued jobs and resumes interrupted ones. Stage outputs use deterministic temporary paths, atomic cache/checkpoint writes, and existing fingerprint-keyed caches so a resumed task can reuse finished units. A GigaChat call with an unknown outcome is not automatically repeated after a crash; it fails safely and requires an explicit retry confirmation to avoid accidental duplicate provider calls.

F3 tests use mocks for provider generation. No real paid provider calls or project migrations are part of this implementation.

## F4 browser integration

On the script step, **Create proposal** records an action and does not call a provider. The confirmation panel shows provider/model and asks for explicit confirmation plus a cost ceiling; cloud proposals additionally require a separate cloud-consent checkbox. Local/demo confirmation uses a zero ceiling and `privacy_scope: "local"`. Non-demo providers require an explicit model ID in settings.

The browser polls the persistent job and restores the latest unresolved action when reopening a project. Running work can be cancelled; failed/cancelled work can be retried only with fresh consent and a current ceiling. Once ready, the browser displays a scene/line diff. The accepted script is read-only while a proposal is unresolved. Apply posts the exact proposal fingerprint and updates the project revision; reject records the decision without changing the accepted script. Manual edits to the accepted script remain separate and continue to save normally.

### Checks and manual smoke test

The browser-state renderer can be checked without a browser using `node tests/test_action_ui.js`; the full server/backend suite is `python -m unittest discover -s tests -v`.

For a manual click-through, use a disposable v2 project:

1. Select the demo provider, create a project, and click **Create proposal**. Confirm that the action appears as proposed and the project revision/script remains unchanged; no generation job should exist yet.
2. Try to launch with the confirmation checkbox clear: it must be blocked. Confirm with the checkbox and zero cost ceiling; the queue/job status should appear.
3. Wait for the candidate diff. Verify the accepted script still has its original revision and text.
4. Reject one candidate and verify the revision is unchanged. Create another candidate, apply it, and verify exactly one new project revision contains the candidate.
5. Reload the project during a queued/running job and verify the status resumes. Optional: cancel a queued job, or retry a failed/cancelled one only after setting fresh confirmation.
6. With GigaChat selected, verify that both cloud acknowledgement and a positive user-entered ceiling are required before the request. Do not run this step against a paid provider unless explicitly authorized.
