# F5 — visual prompts and immutable variant history

F5 adds a local workflow for writing scene-specific visual directions and curating user-supplied image variants. It deliberately does **not** call any image-generation provider. Existing demo-frame generation and v1 behavior remain separate.

## Data and lifecycle

- Current visual description, `prompt.text`, `prompt.negative`, and reference asset IDs live in `production.json.visuals[scene_id]`.
- Saving a changed prompt creates a new project/production revision; the story/spec revision does not change. Writes are optimistic-concurrency guarded with `expected_revision`.
- Uploaded variants are validated PNG/JPEG/WebP and stored as content-addressed immutable assets. The immutable manifest entry snapshots the prompt and input fingerprint that accompanied the upload.
- A newly uploaded variant starts as `created` and is never selected automatically. The user must review it, then explicitly select it or reject it. Selection/deselection updates the production revision and leaves all earlier files and metadata intact.
- Variant state is journal-derived (`created`, `reviewed`, `selected`, `rejected`); file availability/integrity and stale fingerprints are computed separately. If scene/prompt inputs change, the UI marks the stored variant stale but does not delete it. Older image uploads without prompt/fingerprint provenance are labelled `legacy_unverified` rather than presented as fully traceable variants.
- Project v1 is not migrated implicitly; prompt editing and variant history ask for explicit v2 migration.

## API

- `GET /api/projects/{id}/visual-variants[?scene_id=...]` — list per-scene immutable image variants with prompt provenance, lifecycle state, and integrity/staleness.
- `PATCH /api/projects/{id}/visuals/{scene_id}` — save description, prompt, negative prompt, and up to eight same-project image references; body includes `expected_revision`.
- `POST /api/projects/{id}/visual-variants` — upload `{scene_id, expected_revision, data_url, prompt:{text,negative}}`; validates base64/MIME/image dimensions and rejects a stale project revision before appending a candidate image asset.
- `POST /api/projects/{id}/visual-variants/{asset_id}/review` — record explicit review.
- `POST /api/projects/{id}/visual-variants/{asset_id}/select` — select a reviewed variant; body includes `expected_revision`.
- `POST /api/projects/{id}/visual-variants/{asset_id}/reject` — reject without deleting the asset.
- `POST /api/projects/{id}/visual-variants/{asset_id}/deselect` — restore the scene's shared style while retaining the variant in history.

Prompt saves and variant lifecycle decisions are recorded in the append-only action journal. No secrets or provider credentials are stored in prompts or metadata by this workflow.

## Checks

```bash
python -m unittest discover -s tests -v
node tests/test_action_ui.js
```

The tests cover revision boundaries, fingerprint invalidation, immutable provenance, create/review/select/reject/deselect, stale writes, MIME/path-safe API behavior, and rendered UI state. Manual browser click-through on a disposable project is still required before calling F5 fully accepted. No real project migration or paid/cloud image request is part of F5.
