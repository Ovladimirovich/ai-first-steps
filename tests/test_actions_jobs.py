import copy
import json
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory.actions import append_action_event, get_action, verify_action_log
from factory.action_service import apply_action, confirm_action, get_candidate, propose_script_draft
from factory.core import create_project, draft_script, load_project, new_spec, project_dir, save_project
from factory.jobs import (_job_path, _read_job, cancel_job, create_job, get_job, recover_jobs, retry_job, set_executor)
from factory.pipeline import _execute_job, plan, run
from factory.storage import atomic_write_json
from factory.server import Handler

class _TempProjects(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_patch = patch("factory.core.DATA_ROOT", Path(self.tmp.name))
        self.data_patch.start()
        set_executor(_execute_job)

    def tearDown(self):
        set_executor(_execute_job)
        self.data_patch.stop()
        self.tmp.cleanup()

    def wait_job(self, project_id, job_id, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = get_job(job_id, project_id)
            if job and job.get("state") in ("completed", "failed", "cancelled"):
                return job
            time.sleep(0.02)
        self.fail(f"job {job_id} did not reach a terminal state")

class ActionJournalTests(_TempProjects):
    def test_hash_chain_is_verifiable_and_secret_safe(self):
        append_action_event("journal-project", "action_proposed", data={
            "action_id": "a1", "api_key": "TOP-SECRET", "message": "Authorization: Bearer abcdef012345"})
        report = verify_action_log("journal-project")
        self.assertTrue(report["valid"])
        self.assertEqual(report["event_count"], 1)
        path = project_dir("journal-project") / "studio" / "actions.jsonl"
        serialized = path.read_text(encoding="utf-8")
        self.assertNotIn("TOP-SECRET", serialized)
        self.assertNotIn("abcdef012345", serialized)
        self.assertNotIn("api_key", serialized)
        path.write_text(serialized.replace("action_proposed", "action_rejected"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "целостность"):
            verify_action_log("journal-project")

    def test_sequence_rewrite_is_rejected(self):
        append_action_event("journal-project", "one", data={"action_id": "a1"})
        path = project_dir("journal-project") / "studio" / "actions.jsonl"
        event = json.loads(path.read_text(encoding="utf-8"))
        event["sequence"] = 9
        path.write_text(json.dumps(event) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "последовательность"):
            verify_action_log("journal-project")

class ActionLifecycleTests(_TempProjects):
    def test_proposal_candidate_and_apply_are_separate_and_revisioned(self):
        from factory import action_service
        project = create_project({"theme": "Тема сценария", "duration": 30})
        base_revision = project["revision"]
        proposed_spec = draft_script(project["spec"])
        proposed_spec["script"]["scenes"][0]["lines"][0]["text"] = "Текст предложения после проверки."
        with patch.object(action_service, "draft_script", return_value=proposed_spec) as generator:
            proposal = propose_script_draft(project["id"])
            self.assertEqual(load_project(project["id"])["revision"], base_revision)
            generator.assert_not_called()
            with self.assertRaisesRegex(ValueError, "предел стоимости"):
                confirm_action(project["id"], proposal["action_id"], {
                    "input_fingerprint": proposal["input_fingerprint"], "consent": True,
                    "privacy_scope": "local"})
            with self.assertRaisesRegex(ValueError, "отпечатком"):
                confirm_action(project["id"], proposal["action_id"], {
                    "input_fingerprint": "stale", "consent": True, "privacy_scope": "local",
                    "cost_ceiling": {"amount": 0, "currency": "RUB"}})
            job = confirm_action(project["id"], proposal["action_id"], {
                "input_fingerprint": proposal["input_fingerprint"], "consent": True,
                "privacy_scope": "local", "cost_ceiling": {"amount": 0, "currency": "RUB"}})
            self.assertEqual(job["payload"]["base_spec_hash"], proposal["base_spec_hash"])
            self.assertEqual(self.wait_job(project["id"], job["id"])["state"], "completed")
            generator.assert_called_once()
        unchanged = load_project(project["id"])
        self.assertEqual(unchanged["revision"], base_revision)
        self.assertEqual(unchanged["spec"]["script"]["scenes"], [])
        self.assertEqual(get_action(project["id"], proposal["action_id"])["status"], "candidate_ready")
        candidate = get_candidate(project["id"], proposal["action_id"])
        self.assertEqual(candidate["spec"]["script"]["scenes"][0]["lines"][0]["text"],
                         "Текст предложения после проверки.")
        with self.assertRaisesRegex(ValueError, "отпечатком"):
            apply_action(project["id"], proposal["action_id"], {"input_fingerprint": "wrong"})
        result = apply_action(project["id"], proposal["action_id"], {
            "input_fingerprint": proposal["input_fingerprint"]})
        self.assertFalse(result["already_applied"])
        self.assertEqual(result["project"]["revision"], base_revision + 1)
        self.assertEqual(get_action(project["id"], proposal["action_id"])["status"], "applied")
        revision = json.loads((project_dir(project["id"]) / "revisions" /
                               result["project"]["current_revision_id"] / "revision.json").read_text())
        self.assertEqual(revision["action_id"], proposal["action_id"])
        self.assertTrue(apply_action(project["id"], proposal["action_id"], {
            "input_fingerprint": proposal["input_fingerprint"]})["already_applied"])

    def test_paid_cloud_job_requires_consent_and_cost_ceiling(self):
        from factory import action_service
        project = create_project({"theme": "Облачный черновик", "duration": 30})
        settings = {"text_provider": "gigachat", "gigachat_model": "GigaChat-test",
                    "gigachat_cloud_ack": True}
        with patch.object(action_service, "load_settings", return_value=settings), \
             patch.object(action_service, "gigachat_credentials", return_value={"client_id": "id", "client_secret": "secret"}), \
             patch.object(action_service, "draft_with_gigachat", return_value=draft_script(project["spec"])) as provider:
            proposal = propose_script_draft(project["id"])
            self.assertEqual(provider.call_count, 0)
            common = {"input_fingerprint": proposal["input_fingerprint"], "consent": True,
                      "cost_ceiling": {"amount": 10, "currency": "RUB"}}
            with self.assertRaisesRegex(ValueError, "облачного задания"):
                confirm_action(project["id"], proposal["action_id"], common)
            with self.assertRaisesRegex(ValueError, "предел стоимости"):
                confirm_action(project["id"], proposal["action_id"], {
                    "input_fingerprint": proposal["input_fingerprint"], "consent": True,
                    "cloud_consent": True})
            job = confirm_action(project["id"], proposal["action_id"], {**common, "cloud_consent": True})
            self.assertEqual(self.wait_job(project["id"], job["id"])["state"], "completed")
            provider.assert_called_once()
        self.assertEqual(load_project(project["id"])["revision"], project["revision"])

    def test_cloud_call_with_unknown_outcome_is_not_automatically_repeated(self):
        from factory import action_service
        project = create_project({"theme": "Cloud retry", "duration": 30})
        settings = {"text_provider": "gigachat", "gigachat_model": "GigaChat-test",
                    "gigachat_cloud_ack": True}
        set_executor(lambda job: None)
        with (patch.object(action_service, "load_settings", return_value=settings),
              patch.object(action_service, "gigachat_credentials", return_value={"client_id": "id", "client_secret": "secret"}),
              patch.object(action_service, "draft_with_gigachat", side_effect=RuntimeError("mock timeout")) as provider):
            proposal = propose_script_draft(project["id"])
            job = confirm_action(project["id"], proposal["action_id"], {
                "input_fingerprint": proposal["input_fingerprint"], "consent": True,
                "cloud_consent": True, "cost_ceiling": {"amount": 5, "currency": "RUB"}})
            self.assertEqual(self.wait_job(project["id"], job["id"])["state"], "completed")
            persisted = get_job(job["id"], project["id"])
            with self.assertRaisesRegex(RuntimeError, "mock timeout"):
                action_service.execute_script_draft_job(persisted)
            with self.assertRaisesRegex(ValueError, "неизвестен"):
                action_service.execute_script_draft_job(persisted)
            provider.assert_called_once()
        set_executor(_execute_job)

    def test_legacy_projects_are_not_implicitly_migrated_for_actions(self):
        root = project_dir("legacy-project")
        root.mkdir(parents=True)
        metadata = {"id": "legacy-project", "title": "Legacy", "revision": 1}
        spec = new_spec("Legacy action")
        atomic_write_json(root / "project.json", metadata)
        atomic_write_json(root / "spec.json", spec)
        with self.assertRaisesRegex(ValueError, "явную миграцию"):
            propose_script_draft("legacy-project")
        self.assertEqual(json.loads((root / "project.json").read_text()), metadata)
        self.assertFalse((root / "studio" / "actions.jsonl").exists())

    def test_in_place_generator_mutation_preserves_original_candidate_base(self):
        from factory.core import digest
        project = create_project({"theme": "Mutation regression", "duration": 30})
        base_spec = copy.deepcopy(load_project(project["id"])["spec"])
        proposal = propose_script_draft(project["id"])
        job = confirm_action(project["id"], proposal["action_id"], {
            "input_fingerprint": proposal["input_fingerprint"], "consent": True,
            "privacy_scope": "local", "cost_ceiling": {"amount": 0, "currency": "RUB"}})
        self.assertEqual(self.wait_job(project["id"], job["id"])["state"], "completed")
        candidate = get_candidate(project["id"], proposal["action_id"])
        self.assertEqual(candidate["base_spec"], base_spec)
        self.assertEqual(candidate["base_spec_hash"], digest(base_spec))
        self.assertNotEqual(candidate["candidate_spec_hash"], candidate["base_spec_hash"])
        self.assertTrue(candidate["spec"]["script"]["scenes"])

        # Simulate an older candidate whose base was overwritten by the mutating generator.
        from factory.action_service import _publish_candidate
        legacy_candidate = copy.deepcopy(candidate)
        legacy_candidate["base_spec"] = copy.deepcopy(legacy_candidate["spec"])
        legacy_candidate["base_spec_hash"] = legacy_candidate["candidate_spec_hash"]
        _publish_candidate(project["id"], proposal["action_id"], get_action(project["id"], proposal["action_id"]),
                           legacy_candidate, "demo", "rule-v1")
        recovered = get_candidate(project["id"], proposal["action_id"])
        self.assertEqual(recovered["base_spec"], base_spec)
        self.assertEqual(recovered["base_spec_hash"], digest(base_spec))
        applied = apply_action(project["id"], proposal["action_id"], {
            "input_fingerprint": proposal["input_fingerprint"]})
        self.assertTrue(applied["project"]["spec"]["script"]["scenes"])

    def test_apply_rejects_candidate_after_story_change(self):
        from factory import action_service
        project = create_project({"theme": "Stable until review", "duration": 30})
        candidate = draft_script(project["spec"])
        with patch.object(action_service, "draft_script", return_value=candidate):
            proposal = propose_script_draft(project["id"])
            job = confirm_action(project["id"], proposal["action_id"], {
                "input_fingerprint": proposal["input_fingerprint"], "consent": True,
                "privacy_scope": "local", "cost_ceiling": {"amount": 0, "currency": "RUB"}})
            self.assertEqual(self.wait_job(project["id"], job["id"])["state"], "completed")
        changed = load_project(project["id"])
        changed["spec"]["intent"]["theme"] = "Edited during review"
        changed["revision"] += 1
        save_project(changed)
        with self.assertRaisesRegex(ValueError, "Сценарий изменился"):
            apply_action(project["id"], proposal["action_id"], {
                "input_fingerprint": proposal["input_fingerprint"]})

    def test_stale_proposal_fingerprint_is_rejected(self):
        project = create_project({"theme": "Before"})
        proposal = propose_script_draft(project["id"])
        current = load_project(project["id"])
        current["spec"]["intent"]["theme"] = "After"
        current["revision"] += 1
        save_project(current)
        with self.assertRaisesRegex(ValueError, "изменился"):
            confirm_action(project["id"], proposal["action_id"], {
                "input_fingerprint": proposal["input_fingerprint"], "consent": True,
                "privacy_scope": "local", "cost_ceiling": {"amount": 0, "currency": "RUB"}})

class PlanFingerprintTests(_TempProjects):
    def test_plan_survives_restart_storage_and_rejects_stale_renderer_quote(self):
        project = create_project({"theme": "Durable plan", "duration": 30})
        project["spec"] = draft_script(project["spec"])
        project["revision"] += 1
        save_project(project)
        quote = plan(project, "frames")
        plan_file = project_dir(project["id"]) / "studio" / "plans" / f"{quote['id']}.json"
        self.assertTrue(plan_file.is_file())
        self.assertEqual(json.loads(plan_file.read_text())["input_fingerprint"], quote["input_fingerprint"])
        with patch("factory.core.RENDERER_VERSION", "renderer-changed-after-quote"):
            with self.assertRaisesRegex(ValueError, "устарели"):
                run(project, quote["id"], "frames")

class PersistentQueueTests(_TempProjects):
    @staticmethod
    def approval(fingerprint):
        return {"consent": True, "input_fingerprint": fingerprint,
                "cost_ceiling": {"amount": 0, "currency": "EUR"},
                "privacy_scope": "local", "expires_at": time.time() + 3600}

    def test_job_read_retries_transient_windows_file_lock(self):
        project_id, job_id = "read-lock-project", "a" * 32
        path = _job_path(project_id, job_id)
        atomic_write_json(path, {"id": job_id, "project_id": project_id, "state": "queued"})
        original_read_text = Path.read_text
        denied = 0

        def flaky_read_text(file_path, *args, **kwargs):
            nonlocal denied
            if file_path == path and denied < 2:
                denied += 1
                raise PermissionError("temporary Windows sharing violation")
            return original_read_text(file_path, *args, **kwargs)

        with patch.object(Path, "read_text", flaky_read_text):
            result = _read_job(project_id, job_id)
        self.assertEqual(result["state"], "queued")
        self.assertEqual(denied, 2)

    def test_one_worker_cancel_and_retry(self):
        first_started, release_first = threading.Event(), threading.Event()
        state_lock = threading.Lock()
        active = maximum = 0
        attempts = {}

        def executor(job):
            nonlocal active, maximum
            with state_lock:
                active += 1
                maximum = max(maximum, active)
                attempts[job["id"]] = attempts.get(job["id"], 0) + 1
            try:
                if job["payload"].get("block"):
                    first_started.set()
                    release_first.wait(3)
                if job["payload"].get("fail_once") and attempts[job["id"]] == 1:
                    raise RuntimeError("mock failure")
            finally:
                with state_lock:
                    active -= 1

        set_executor(executor)
        first = create_job("queue-project", action_id="a1", job_type="mock", payload={"block": True},
                           input_fingerprint="fp1", approval=self.approval("fp1"))
        self.assertTrue(first_started.wait(2))
        second = create_job("queue-project", action_id="a2", job_type="mock", payload={},
                            input_fingerprint="fp2", approval=self.approval("fp2"))
        self.assertEqual(cancel_job("queue-project", second["id"])["state"], "cancelled")
        release_first.set()
        self.assertEqual(self.wait_job("queue-project", first["id"])["state"], "completed")
        self.assertEqual(get_job(second["id"], "queue-project")["state"], "cancelled")
        failed = create_job("queue-project", action_id="a3", job_type="mock", payload={"fail_once": True},
                            input_fingerprint="fp3", approval=self.approval("fp3"))
        self.assertEqual(self.wait_job("queue-project", failed["id"])["state"], "failed")
        retry_job("queue-project", failed["id"], input_fingerprint="fp3",
                  approval=self.approval("fp3"))
        self.assertEqual(self.wait_job("queue-project", failed["id"])["state"], "completed")
        self.assertEqual(get_job(failed["id"], "queue-project")["retry_count"], 1)
        self.assertEqual(maximum, 1)

    def test_recovery_never_runs_a_job_without_journaled_confirmation(self):
        job = {"id": "unconfirmed1", "project_id": "unconfirmed", "action_id": "action-unconfirmed",
               "job_type": "mock", "stage": None, "kind": None, "payload": {},
               "input_fingerprint": "fp-unconfirmed", "state": "queued", "progress": 0,
               "message": "queued", "log": [], "checkpoint": None, "cancel_requested": False,
               "retry_count": 0, "recovery_count": 0, "created_at": time.time(),
               "started_at": None, "updated_at": time.time(), "finished_at": None,
               "error": None, "approval": self.approval("fp-unconfirmed")}
        append_action_event(job["project_id"], "action_proposed", data={"action_id": job["action_id"]})
        append_action_event(job["project_id"], "job_queued", actor="system",
                            data={"action_id": job["action_id"], "job_id": job["id"]})
        atomic_write_json(_job_path(job["project_id"], job["id"]), job)
        called = []
        set_executor(lambda value: called.append(value["id"]))
        self.assertEqual(recover_jobs()["queued"], 0)
        time.sleep(0.05)
        self.assertEqual(called, [])
        self.assertEqual(get_job(job["id"], job["project_id"])["state"], "queued")

    def test_running_job_honors_cancel_request(self):
        started, release = threading.Event(), threading.Event()

        def slow_executor(job):
            started.set()
            release.wait(3)
            from factory.jobs import is_cancel_requested
            if is_cancel_requested(job["project_id"], job["id"]):
                from factory.jobs import JobCancelled
                raise JobCancelled()

        set_executor(slow_executor)
        job = create_job("cancel-running", action_id="cancel-action", job_type="mock", payload={},
                         input_fingerprint="cancel-fp", approval=self.approval("cancel-fp"))
        self.assertTrue(started.wait(2))
        self.assertTrue(cancel_job("cancel-running", job["id"])["cancel_requested"])
        release.set()
        self.assertEqual(self.wait_job("cancel-running", job["id"])["state"], "cancelled")

    def test_restart_requeues_interrupted_job_with_checkpoint(self):
        checkpoint = {"stage": "frame", "completed": 1, "total": 3, "fingerprint": "fp"}
        job = {"id": "abc123", "project_id": "recovery-project", "action_id": "recovery-action",
               "job_type": "mock", "stage": "frames", "kind": None, "payload": {},
               "input_fingerprint": "recover-fp", "state": "running", "progress": 40,
               "message": "interrupted", "log": [], "checkpoint": checkpoint,
               "cancel_requested": False, "retry_count": 0, "recovery_count": 0,
               "created_at": time.time(), "started_at": time.time(), "updated_at": time.time(),
               "finished_at": None, "error": None, "approval": self.approval("recover-fp")}
        append_action_event(job["project_id"], "action_proposed", data={
            "action_id": job["action_id"], "kind": "mock", "input_fingerprint": job["input_fingerprint"]})
        append_action_event(job["project_id"], "action_confirmed", actor="user",
                            data={"action_id": job["action_id"], "job_id": job["id"], "confirmation": job["approval"]})
        append_action_event(job["project_id"], "job_queued", actor="system",
                            data={"action_id": job["action_id"], "job_id": job["id"]})
        atomic_write_json(_job_path(job["project_id"], job["id"]), job)
        observed = []
        set_executor(lambda current: observed.append(current.get("checkpoint")))
        self.assertEqual(recover_jobs()["interrupted"], 1)
        finished = self.wait_job(job["project_id"], job["id"])
        self.assertEqual(finished["state"], "completed")
        self.assertEqual(finished["recovery_count"], 1)
        self.assertEqual(observed, [checkpoint])

class ActionApiTests(_TempProjects):
    def setUp(self):
        super().setUp()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.project = create_project({"theme": "API actions", "duration": 30})

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        super().tearDown()

    def request(self, path, method="GET", body=None):
        import urllib.error
        import urllib.request
        data = json.dumps(body or {}).encode() if method != "GET" else None
        request = urllib.request.Request(self.base + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode())

    def test_job_read_errors_return_json_instead_of_server_traceback(self):
        with patch("factory.server.get_job", side_effect=ValueError("Файл задачи временно недоступен для чтения")):
            status, result = self.request(f"/api/projects/{self.project['id']}/jobs/{'a' * 32}")
        self.assertEqual(status, 503)
        self.assertIn("временно недоступен", result["error"])

    def test_action_endpoints_and_legacy_job_state_mapping(self):
        from factory import action_service
        candidate = draft_script(self.project["spec"])
        with patch.object(action_service, "draft_script", return_value=candidate):
            legacy_status, legacy_error = self.request(f"/api/projects/{self.project['id']}/script-draft", "POST", {})
            self.assertEqual(legacy_status, 409)
            self.assertIn("/actions", legacy_error["error"])
            status, proposal = self.request(f"/api/projects/{self.project['id']}/actions", "POST", {})
            self.assertEqual(status, 201)
            self.assertEqual(self.request(f"/api/projects/{self.project['id']}")[1]["revision"],
                             self.project["revision"])
            status, denied = self.request(f"/api/projects/{self.project['id']}/actions/{proposal['action_id']}/confirm",
                                          "POST", {"input_fingerprint": proposal["input_fingerprint"]})
            self.assertEqual(status, 400)
            self.assertIn("подтверждение", denied["error"].lower())
            current = self.request(f"/api/projects/{self.project['id']}")[1]
            status, metadata_before_confirm = self.request(f"/api/projects/{self.project['id']}", "PATCH", {
                "revision": current["revision"], "spec": current["spec"], "current_step": 1})
            self.assertEqual(status, 200)
            self.assertGreater(metadata_before_confirm["revision"], current["revision"])
            status, job = self.request(f"/api/projects/{self.project['id']}/actions/{proposal['action_id']}/confirm",
                                       "POST", {"input_fingerprint": proposal["input_fingerprint"],
                                                "consent": True, "privacy_scope": "local",
                                                "cost_ceiling": {"amount": 0, "currency": "RUB"}})
            self.assertEqual(status, 202)
            queue_listing = self.request(f"/api/projects/{self.project['id']}/jobs")[1]["jobs"]
            self.assertTrue(any(item["id"] == job["id"] for item in queue_listing))
            deadline = time.monotonic() + 8
            action = {}
            while time.monotonic() < deadline:
                _, action = self.request(f"/api/projects/{self.project['id']}/actions/{proposal['action_id']}")
                if action.get("status") == "candidate_ready":
                    break
                time.sleep(0.02)
            self.assertEqual(action.get("status"), "candidate_ready")
            self.assertEqual(self.wait_job(self.project["id"], job["id"])["state"], "completed")
            current = self.request(f"/api/projects/{self.project['id']}")[1]
            status, metadata_save = self.request(f"/api/projects/{self.project['id']}", "PATCH", {
                "revision": current["revision"], "spec": current["spec"], "current_step": 2})
            self.assertEqual(status, 200)
            self.assertGreater(metadata_save["revision"], current["revision"])
            status, job_detail = self.request(f"/api/projects/{self.project['id']}/jobs/{job['id']}")
            self.assertEqual(status, 200)
            self.assertEqual(job_detail["state"], "completed")
            _, legacy_job = self.request(f"/api/projects/{self.project['id']}/jobs?id={job['id']}")
            self.assertEqual(legacy_job["state"], "done")
            status, applied = self.request(f"/api/projects/{self.project['id']}/actions/{proposal['action_id']}/apply",
                                           "POST", {"input_fingerprint": proposal["input_fingerprint"]})
            self.assertEqual(status, 200)
            self.assertEqual(applied["project"]["revision"], metadata_save["revision"] + 1)
            journal = self.request(f"/api/projects/{self.project['id']}/actions")[1]
            self.assertTrue(journal["valid"])
            self.assertEqual(journal["actions"][0]["status"], "applied")

if __name__ == "__main__":
    unittest.main()
