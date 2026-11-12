# -*- coding: utf-8 -*-
r"""E2E driver: idea -> scene -> AgnesImage (one request per scene) -> piper TTS -> MP4
Against the local Factory (HEAD 5464099, branch arena/c0c3d897-ai-first-steps) on http://localhost:7860.
Run: C:\Projects_arena\ai-first-steps\.venv\Scripts\python.exe c:\Projects_arena\ai-first-steps\e2e\factory_e2e_driver.py <project_id>

Quality pass (v2):
- clean, meaningful script lines (no test markers);
- AgnesImage generated backgrounds for ALL scenes (no placeholder uploads);
- one AgnesImage request per scene (image-plan -> image-run -> variant select).
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = "http://localhost:7860"
LOG = Path(r"c:\Projects_arena\factory_e2e_driver.log")
_log_lines = []

# Clean narration per scene (heroes: h1 = Матрёна, h2 = Виктор).
CLEAN_LINES = {
    "s1": [
        {"hero": "h2", "text": "Почему нейросети делают науку ближе к каждому из нас?"},
        {"hero": "h1", "text": "Отличный вопрос! Сейчас разложим эту тему на простые части."},
    ],
    "s2": [
        {"hero": "h1", "text": "Представь команду: нейросеть изучает сотни статей и находит то, что легко пропустить самому."},
    ],
    "s3": [
        {"hero": "h2", "text": "Расскажи об этом кому-нибудь сегодня — и увидимся в новом выпуске!"},
    ],
}

STYLE = ("warm 3D cartoon, pixar style, soft window light, bright colors, "
         "4:3 composition, no text, no watermark")
PROMPTS = {
    "s1": ("Cartoon 3D scene: a friendly turquoise cube robot and a curious schoolgirl "
           "with a backpack in a warm inventor workshop, shelves with jars and blueprints. " + STYLE),
    "s2": ("Cartoon 3D scene: the same turquoise cube robot shows the schoolgirl a giant "
           "open book with glowing floating pages, warm workshop background. " + STYLE),
    "s3": ("Cartoon 3D scene: the turquoise cube robot and the schoolgirl waving goodbye "
           "on a sunny street with soft evening light. " + STYLE),
}


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    _log_lines.append(line)


def http(method: str, path: str, body=None, timeout: int = 30):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw.decode("utf-8"))
            except ValueError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw.decode("utf-8"))
        except ValueError:
            return exc.code, raw.decode("utf-8", "replace")


def poll_job(project_id: str, job_id: str, timeout_s: int = 900) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status, job = http("GET", f"/api/projects/{project_id}/jobs/{job_id}")
        if status != 200:
            raise RuntimeError(f"job read failed: {status} {job}")
        state = job.get("state")
        log(f"    job {job_id[:12]}... state={state} progress={job.get('progress', 0)}% "
            f"msg={str(job.get('message', ''))[:120]!r}")
        if state in ("completed", "failed", "cancelled"):
            return job
        time.sleep(5)
    raise TimeoutError(f"job {job_id} not finished in {timeout_s}s")


def local_confirmation() -> dict:
    return {"max_cost": 0, "currency": "EUR", "privacy_scope": "local", "consent": True}


def cloud_free_quota_confirmation() -> dict:
    return {
        "max_cost": 0, "currency": "EUR",
        "privacy_scope": "cloud", "consent": True, "cloud_consent": True,
        "billing_mode": "free_quota", "daily_quota_ack": True,
    }


def main() -> None:
    project_id = sys.argv[1]

    # 1) project state
    status, proj = http("GET", f"/api/projects/{project_id}")
    assert status == 200, f"GET project failed: {status} {proj}"
    spec = proj["spec"]
    scenes = spec["script"]["scenes"]
    log(f"project {project_id} rev={proj['revision']} scenes={len(scenes)}")
    for scene in scenes:
        lines = scene.get("lines") or scene.get("script") or []
        log(f"  scene {scene['id']} [{scene.get('order')}] {scene.get('title')} lines={len(lines)}")

    # 1b) if the script is empty, produce it via the script-draft action (demo provider, offline)
    if not scenes:
        # Reuse an existing candidate-ready draft action when present (left by a previous run)
        status, actions_view = http("GET", f"/api/projects/{project_id}/actions")
        ready = next((a for a in actions_view.get("actions", [])
                      if a.get("kind") == "script-draft" and a.get("status") == "candidate_ready"), None)
        if ready is not None:
            action_id = ready["action_id"]
            input_fingerprint = (ready.get("candidate") or {}).get("input_fingerprint") or ready.get("input_fingerprint")
            log(f"reusing ready script-draft action {action_id}")
        else:
            log("script empty -> running script-draft action (demo provider)")
            status, act = http("POST", f"/api/projects/{project_id}/actions", {"kind": "script-draft"})
            assert status == 201, f"script-draft propose failed: {status} {act}"
            action_id = act["action_id"]
            input_fingerprint = act["input_fingerprint"]
            log(f"script-draft proposed: provider={act.get('provider')} scope={act.get('privacy_scope')}")
            status, confirm_job = http("POST", f"/api/projects/{project_id}/actions/{action_id}/confirm", {
                "input_fingerprint": input_fingerprint, "consent": True,
                "cost_ceiling": {"amount": 0, "currency": "RUB"}, "privacy_scope": "local",
            })
            assert status == 202, f"script-draft confirm failed: {status} {confirm_job}"
            confirm_job = poll_job(project_id, confirm_job["id"], timeout_s=300)
            assert confirm_job.get("state") == "completed", f"draft job failed: {confirm_job.get('state')} error={confirm_job.get('error')}"
        status, act2 = http("GET", f"/api/projects/{project_id}/actions/{action_id}")
        assert status == 200, f"action read failed: {status} {act2}"
        assert act2.get("status") in ("candidate_ready", "apply_pending"), f"draft not ready: {act2.get('status')}"
        candidate = act2.get("candidate_spec")
        log(f"draft candidate: scenes={len((candidate or {}).get('script', {}).get('scenes', []))}")
        status, cur = http("GET", f"/api/projects/{project_id}")
        status, applied = http("POST", f"/api/projects/{project_id}/actions/{action_id}/apply",
                               {"expected_revision": cur["revision"], "input_fingerprint": input_fingerprint})
        assert status == 200, f"apply failed: {status} {applied}"
        log(f"draft applied -> project revision {applied['project']['revision']}")
        status, proj = http("GET", f"/api/projects/{project_id}")
        spec = proj["spec"]
        scenes = spec["script"]["scenes"]
        assert scenes, "script-draft produced no scenes"
        for scene in scenes:
            lines = scene.get("lines") or scene.get("script") or []
            log(f"  scene {scene['id']} [{scene.get('order')}] {scene.get('title')} lines={len(lines)}")

    # 2) clean script: replace every line with meaningful narration (no test markers)
    status, proj = http("GET", f"/api/projects/{project_id}")
    spec = proj["spec"]
    scenes = spec["script"]["scenes"]
    edited = json.loads(json.dumps(spec))
    for scene in edited["script"]["scenes"]:
        sid = str(scene.get("id"))
        clean = CLEAN_LINES.get(sid)
        if clean is None:
            log(f"warning: no clean lines prepared for scene {sid}; keeping original")
            continue
        lines_key = "lines" if "lines" in scene else "script"
        original = scene.get(lines_key) or []
        rebuilt = []
        for idx, item in enumerate(clean):
            entry = dict(item)
            if idx < len(original) and isinstance(original[idx], dict) and str(original[idx].get("id", "")):
                entry["id"] = str(original[idx]["id"])
            else:
                entry["id"] = f"{sid[1:]}{idx + 1}"
            rebuilt.append(entry)
        scene[lines_key] = rebuilt
    status, patched = http("PATCH", f"/api/projects/{project_id}", {
        "revision": proj["revision"], "spec": edited, "current_step": 2,
    })
    assert status == 200, f"PATCH spec failed: {status} {patched}"
    log(f"clean script saved: revision {proj['revision']} -> {patched['revision']} current_step=2")

    # 3..7) per-scene AgnesImage backgrounds: prompt -> plan -> run -> select the fresh variant
    for scene in scenes:
        sid = str(scene["id"])
        assert sid in PROMPTS, f"no visual prompt prepared for scene {sid}"
        status, proj = http("GET", f"/api/projects/{project_id}")
        status, updated = http("PATCH", f"/api/projects/{project_id}/visuals/{sid}", {
            "prompt": PROMPTS[sid], "expected_revision": proj["revision"],
        })
        assert status == 200, f"PATCH visuals {sid} failed: {status} {updated}"
        log(f"prompt saved for scene {sid}: unchanged={updated.get('unchanged')}")

        status, plan_entry = http("POST", f"/api/projects/{project_id}/image-plan", {"kind": sid})
        assert status == 200, f"image-plan {sid} failed: {status} {plan_entry}"
        log(f"image-plan {sid}: provider={plan_entry.get('provider')} billing={plan_entry.get('billing_mode')} "
            f"cost={plan_entry.get('cost')} EUR scope={plan_entry.get('privacy_scope')}")
        assert plan_entry.get("provider") == "comfyui_agnes"
        assert plan_entry.get("billing_mode") == "free_quota"

        status, job = http("POST", f"/api/projects/{project_id}/image-run", {
            "plan_id": plan_entry["id"], "kind": sid,
            "confirmation": cloud_free_quota_confirmation(),
        })
        assert status == 202, f"image-run {sid} failed: {status} {job}"
        log(f"image-run {sid} queued: job={job['id']} state={job.get('state')}")
        job = poll_job(project_id, job["id"], timeout_s=600)
        assert job.get("state") == "completed", (f"image job {sid} failed: {job.get('state')} "
                                                f"error={job.get('error')} logs={job.get('log')[-6:]}")
        log(f"image job {sid} completed: {job.get('message')}")

        status, variants = http("GET", f"/api/projects/{project_id}/visual-variants?scene_id={sid}")
        assert status == 200, f"visual-variants {sid} failed: {status} {variants}"
        items = variants.get("variants", []) if isinstance(variants, dict) else variants
        for item in items:
            log(f"  {sid} variant {item.get('asset_id')} source={item.get('source')} "
                f"v{item.get('asset_version')} stale={item.get('stale')}")
        fresh = [item for item in items if item.get("source") == "generated" and not item.get("stale")]
        pool = fresh or items
        assert pool, f"no visual variant found for scene {sid}"
        chosen = pool[-1]
        asset_id = str(chosen.get("asset_id"))
        status, reviewed = http("POST", f"/api/projects/{project_id}/visual-variants/{asset_id}/review", {})
        assert status == 200, f"variant review {sid} failed: {status} {reviewed}"
        log(f"variant reviewed: asset={asset_id}")
        status, cur = http("GET", f"/api/projects/{project_id}")
        status, sel = http("POST", f"/api/projects/{project_id}/visual-variants/{asset_id}/select",
                           {"expected_revision": cur["revision"]})
        assert status == 200, f"variant select {sid} failed: {status} {sel}"
        log(f"variant selected for scene {sid}: {json.dumps(sel, ensure_ascii=False)[:220]}")

    # 8) voice plan + run (piper)
    status, vplan = http("POST", f"/api/projects/{project_id}/voice-plan", {})
    assert status == 200, f"voice-plan failed: {status} {vplan}"
    log(f"voice-plan: units={vplan.get('units')}/{vplan.get('total_units')} msg={vplan.get('message')}")
    status, vjob = http("POST", f"/api/projects/{project_id}/voice-run", {
        "plan_id": vplan["id"], "confirmation": local_confirmation(),
    })
    assert status == 202, f"voice-run failed: {status} {vjob}"
    vjob = poll_job(project_id, vjob["id"], timeout_s=600)
    assert vjob.get("state") == "completed", f"voice job failed: {vjob.get('state')} error={vjob.get('error')} logs={vjob.get('log')[-6:]}"
    log(f"voice job completed: {vjob.get('message')}")

    # 9) frames
    status, fplan = http("POST", f"/api/projects/{project_id}/frames-plan", {})
    assert status == 200, f"frames-plan failed: {status} {fplan}"
    status, fjob = http("POST", f"/api/projects/{project_id}/frames-run", {
        "plan_id": fplan["id"], "confirmation": local_confirmation(),
    })
    assert status == 202, f"frames-run failed: {status} {fjob}"
    fjob = poll_job(project_id, fjob["id"], timeout_s=600)
    assert fjob.get("state") == "completed", f"frames job failed: {fjob.get('state')} error={fjob.get('error')} logs={fjob.get('log')[-6:]}"
    log(f"frames job completed: {fjob.get('message')}")

    # 10) render final MP4
    status, rplan = http("POST", f"/api/projects/{project_id}/render-plan", {"kind": "final"})
    assert status == 200, f"render-plan failed: {status} {rplan}"
    log(f"render-plan: {rplan.get('message')}")
    status, rjob = http("POST", f"/api/projects/{project_id}/render-run", {
        "plan_id": rplan["id"], "kind": "final", "confirmation": local_confirmation(),
    })
    assert status == 202, f"render-run failed: {status} {rjob}"
    rjob = poll_job(project_id, rjob["id"], timeout_s=1800)
    assert rjob.get("state") == "completed", f"render job failed: {rjob.get('state')} error={rjob.get('error')} logs={rjob.get('log')[-8:]}"
    log(f"render job completed: {rjob.get('message')}")

    # 11) verify MP4 on disk
    mp4 = Path(r"C:\Projects_arena\ai-first-steps-agnes\.factory\projects") / project_id / "renders" / "final.mp4"
    assert mp4.is_file() and mp4.stat().st_size > 0, f"final.mp4 missing: {mp4}"
    log(f"final.mp4 exists: {mp4} ({mp4.stat().st_size // 1024} KB)")

    # 12) artifact state
    status, art = http("GET", f"/api/projects/{project_id}/artifacts")
    if status == 200:
        log(f"artifacts: {json.dumps(art, ensure_ascii=False)[:400]}")

    LOG.write_text("\n".join(_log_lines), encoding="utf-8")
    log("E2E DONE")


if __name__ == "__main__":
    main()

