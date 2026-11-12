# -*- coding: utf-8 -*-
r"""E2E driver: idea -> scene -> local render smoke (piper TTS -> MP4)
Against the local Factory (HEAD 5464099, branch arena/c0c3d897-ai-first-steps) on http://localhost:7860.
Run: C:\Projects_arena\ai-first-steps\.venv\Scripts\python.exe c:\Projects_arena\ai-first-steps\e2e\factory_e2e_driver.py <project_id>

Quality pass (v2):
- clean, meaningful script lines (no test markers);
- background images uploaded from existing active-scene-backgrounds/ (no Agnes/ComfyUI generation);
- local voice (piper), local frames, local final MP4 render.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

# Force UTF-8 for Windows console (cp1251) — prevents UnicodeEncodeError on ₽ etc.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

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
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        # Windows console cp1251 doesn't support ₽ and other symbols
        print(line.encode('cp1251', 'replace').decode('cp1251'), flush=True)
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
        "privacy_scope": "cloud_free", "consent": True, "cloud_consent": True,
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

    # 1b) if the script is empty, fail fast — cloud-free smoke must not spend
    # cloud quota on script generation. Provide a project with scenes already.
    if not scenes:
        raise SystemExit(
            "E2E cloud-free smoke requires a project with scenes already present; "
            "refusing to run script-draft (would spend cloud quota)."
        )

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

        import base64
        bg_dir = Path(r"C:\Projects_arena\ai-first-steps\.factory\projects") / project_id / "active-scene-backgrounds"
        # find the actual background file (may be .jpg or .png despite extension)
        bg_file = None
        for ext in (".jpg", ".png", ".jpeg", ".webp"):
            candidate = bg_dir / f"{sid}{ext}"
            if candidate.is_file():
                bg_file = candidate
                break
        assert bg_file is not None, f"no background image for scene {sid} in {bg_dir}"
        raw = bg_file.read_bytes()
        # detect MIME from file signature
        if raw[:4] == b'\x89PNG':
            mime = "image/png"
        elif raw[:3] == b'\xff\xd8\xff':
            mime = "image/jpeg"
        elif raw[:4] == b'RIFF' and len(raw) > 12 and raw[8:12] == b'WEBP':
            mime = "image/webp"
        else:
            mime = "application/octet-stream"
        b64 = base64.b64encode(raw).decode("ascii")
        data_url = f"data:{mime};base64,{b64}"
        log(f"uploading existing background for scene {sid}: {bg_file.name} ({len(raw)} bytes) {mime}")
        status, created = http("POST", f"/api/projects/{project_id}/visual-variants", {
            "scene_id": sid,
            "expected_revision": proj["revision"],
            "data_url": data_url,
            "prompt": {"text": PROMPTS[sid], "negative": ""},
        })
        assert status in (200, 201), f"variant upload {sid} failed: {status} {created}"
        log(f"variant uploaded for scene {sid}")

        status, variants = http("GET", f"/api/projects/{project_id}/visual-variants?scene_id={sid}")
        assert status == 200, f"visual-variants {sid} failed: {status} {variants}"
        items = variants.get("variants", []) if isinstance(variants, dict) else variants
        for item in items:
            log(f"  {sid} variant {item.get('asset_id')} source={item.get('source')} "
                f"v{item.get('asset_version')} stale={item.get('stale')}")
        fresh = [item for item in items if item.get("source") == "uploaded" and not item.get("stale")]
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
    mp4 = Path(r"C:\Projects_arena\ai-first-steps\.factory\projects") / project_id / "renders" / "final.mp4"
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

