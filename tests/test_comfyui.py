import base64
import json
import sys
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory.comfyui import (ComfyUIError, check_comfyui_connection,
                             generate_agnes_txt2img, generate_local_txt2img,
                             inspect_agnes_connection, normalize_comfyui_base_url)
from factory.jobs import JobCancelled
from factory.server import Handler
from factory.settings import save_settings


class FakeComfyUIHandler(BaseHTTPRequestHandler):
    requests = []
    redirect_stats = False
    submitted_workflow = None
    cancel_queued = False
    agnes_mode = False
    node_errors = False
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p7sAAAAASUVORK5CYII=")

    def do_GET(self):
        type(self).requests.append((self.command, self.path))
        if self.path.startswith("/history/"):
            if type(self).agnes_mode:
                payload = {"test-prompt-1": {"status": {"status_str": "success", "completed": True},
                                             "outputs": {"3": {"images": [{"filename": "test-agnes.png", "subfolder": "", "type": "temp"}]}}}}
            else:
                payload = {"test-prompt-1": {"status": {"status_str": "success", "completed": True},
                                             "outputs": {"7": {"images": [{"filename": "test.png", "subfolder": "", "type": "output"}]}}}}
        elif self.path.startswith("/view?"):
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(type(self).png)))
            self.end_headers()
            self.wfile.write(type(self).png)
            return
        elif self.path == "/queue":
            pending = [[1, "test-prompt-1", {}, {}, []]] if type(self).cancel_queued else []
            payload = {"queue_running": [], "queue_pending": pending}
        elif self.path == "/system_stats" and type(self).redirect_stats:
            self.send_response(302)
            self.send_header("Location", "http://example.com/should-not-be-requested")
            self.end_headers()
            return
        if self.path == "/system_stats":
            payload = {"system": {"os": "test-os", "python_version": "3.12", "pytorch_version": "2.5"},
                       "devices": [{"name": "CPU"}]}
        elif self.path == "/object_info":
            payload = {
                "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["model-a.safetensors"]]}},
                                            "output": ["MODEL", "CLIP", "VAE"],
                                            "output_name": ["MODEL", "CLIP", "VAE"]},
                "CLIPTextEncode": {"input": {"required": {"text": ["STRING"], "clip": ["CLIP"]}},
                                   "output": ["CONDITIONING"], "output_name": ["CONDITIONING"]},
                "EmptyLatentImage": {"input": {"required": {"width": ["INT"], "height": ["INT"], "batch_size": ["INT"]}},
                                     "output": ["LATENT"], "output_name": ["LATENT"]},
                "KSampler": {"input": {"required": {
                    "seed": ["INT"], "steps": ["INT"], "cfg": ["FLOAT"],
                    "sampler_name": [["euler"]], "scheduler": [["normal"]], "denoise": ["FLOAT"],
                    "model": ["MODEL"], "positive": ["CONDITIONING"], "negative": ["CONDITIONING"],
                    "latent_image": ["LATENT"]}}, "output": ["LATENT"], "output_name": ["LATENT"]},
                "VAEDecode": {"input": {"required": {"samples": ["LATENT"], "vae": ["VAE"]}},
                              "output": ["IMAGE"], "output_name": ["IMAGE"]},
                "SaveImage": {"input": {"required": {"images": ["IMAGE"], "filename_prefix": ["STRING"]}}},
                "PreviewImage": {"input": {"required": {"images": ["IMAGE"]},
                                           "optional": {"prompt": ["STRING"], "extra_pnginfo": ["DICTIONARY"]}},
                                 "output": ["IMAGE"], "output_name": ["IMAGE"]},
                "AgnesImage": {"input": {"required": {
                    "prompt": ["STRING"],
                    "quality": [["1K", "2K", "3K", "4K"]],
                    "aspect_ratio": [["auto", "1:1", "4:3", "16:9"]],
                    "seed": ["INT", {"default": 0, "min": 0, "max": 18446744073709551615,
                                      "control_after_generate": True}]}},
                              "output": ["IMAGE"], "output_name": ["images"]},
                "AgnesText": {"input": {"required": {
                    "preset": [["Prompt Enhance", "Translate to English"]],
                    "prompt": ["STRING"],
                    "seed": ["INT", {"default": 0, "min": 0, "max": 18446744073709551615}]}},
                             "output": ["STRING"], "output_name": ["output"]},
                "OtherNode": {},
            }
        elif not (self.path.startswith("/history/") or self.path == "/queue"):
            self.send_error(404)
            return
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args):
        pass

    def do_POST(self):
        type(self).requests.append((self.command, self.path))
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        if self.path == "/prompt":
            type(self).submitted_workflow = json.loads(body)
            payload = {"prompt_id": "test-prompt-1"}
            if type(self).node_errors:
                payload["node_errors"] = {"13": ["AgnesImage: unknown quality"]}
        elif self.path == "/queue":
            payload = {"deleted": json.loads(body).get("delete", [])}
        else:
            self.send_error(405)
            return
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class ComfyUITests(unittest.TestCase):
    def setUp(self):
        FakeComfyUIHandler.requests = []
        FakeComfyUIHandler.redirect_stats = False
        FakeComfyUIHandler.submitted_workflow = None
        FakeComfyUIHandler.cancel_queued = False
        FakeComfyUIHandler.agnes_mode = False
        FakeComfyUIHandler.node_errors = False
        self.comfy_server = ThreadingHTTPServer(("127.0.0.1", 0), FakeComfyUIHandler)
        self.comfy_thread = Thread(target=self.comfy_server.serve_forever, daemon=True)
        self.comfy_thread.start()
        self.base_url = f"http://127.0.0.1:{self.comfy_server.server_port}"

    def tearDown(self):
        self.comfy_server.shutdown()
        self.comfy_server.server_close()
        self.comfy_thread.join(timeout=2)

    def test_local_url_normalization_and_remote_rejection(self):
        self.assertEqual(normalize_comfyui_base_url(" http://localhost:8188/ "), "http://localhost:8188")
        self.assertEqual(normalize_comfyui_base_url("http://[::1]:8188"), "http://[::1]:8188")
        for address in ("https://example.com", "http://192.168.1.10:8188", "file:///tmp", "http://localhost:8188/path", "http://localhost:bad-port"):
            with self.subTest(address=address), self.assertRaises(ComfyUIError):
                normalize_comfyui_base_url(address)

    def test_connection_reads_stats_and_node_info_without_submitting_workflow(self):
        result = check_comfyui_connection({"comfyui_base_url": self.base_url})
        self.assertTrue(result["connected"])
        self.assertEqual(result["node_count"], 10)
        self.assertEqual(result["nodes"], {"CheckpointLoaderSimple": True, "KSampler": True,
                                            "AgnesImage": True, "AgnesText": True})
        self.assertEqual(result["system"]["device_count"], 1)
        self.assertEqual(FakeComfyUIHandler.requests, [("GET", "/system_stats"), ("GET", "/object_info")])

    def test_redirect_from_local_api_is_not_followed(self):
        FakeComfyUIHandler.redirect_stats = True
        with self.assertRaisesRegex(ComfyUIError, "302"):
            check_comfyui_connection({"comfyui_base_url": self.base_url})
        self.assertEqual(FakeComfyUIHandler.requests, [("GET", "/system_stats")])

    def test_local_profile_api_lists_live_checkpoint_and_sampler_choices(self):
        with patch("factory.server.load_settings", return_value={"comfyui_base_url": self.base_url}):
            app_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            app_thread = Thread(target=app_server.serve_forever, daemon=True)
            app_thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{app_server.server_port}/api/settings/comfyui/local-profile") as response:
                    result = json.loads(response.read())
                self.assertEqual(result["profile_id"], "comfyui-core-txt2img-v1")
                self.assertEqual(result["models"], ["model-a.safetensors"])
                self.assertEqual(result["samplers"], ["euler"])
                self.assertEqual(FakeComfyUIHandler.requests, [("GET", "/object_info")])
            finally:
                app_server.shutdown()
                app_server.server_close()
                app_thread.join(timeout=2)

    def test_local_workflow_export_returns_graph_without_submitting_it(self):
        settings = {"comfyui_base_url": self.base_url, "comfyui_local_model": "model-a.safetensors"}
        with patch("factory.server.load_settings", return_value=settings):
            app_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            app_thread = Thread(target=app_server.serve_forever, daemon=True)
            app_thread.start()
            try:
                body = {"model": "model-a.safetensors", "prompt": "A paper boat on a pond",
                        "negative_prompt": "text", "seed": 42, "width": 512, "height": 512,
                        "steps": 20, "cfg": 7.0}
                request = Request(f"http://127.0.0.1:{app_server.server_port}/api/settings/comfyui/local-profile/workflow",
                                  data=json.dumps(body).encode("utf-8"),
                                  headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(request) as response:
                    result = json.loads(response.read())
                self.assertFalse(result["submitted"])
                self.assertEqual(result["profile_id"], "comfyui-core-txt2img-v1")
                self.assertEqual(len(result["prompt"]), 7)
                self.assertEqual(result["prompt"]["1"]["inputs"]["ckpt_name"], "model-a.safetensors")
                self.assertEqual(FakeComfyUIHandler.requests, [("GET", "/object_info")])

                body["model"] = "another-model.safetensors"
                bad = Request(f"http://127.0.0.1:{app_server.server_port}/api/settings/comfyui/local-profile/workflow",
                              data=json.dumps(body).encode("utf-8"),
                              headers={"Content-Type": "application/json"}, method="POST")
                with self.assertRaises(HTTPError) as error:
                    urlopen(bad)
                self.assertEqual(error.exception.code, 400)
                self.assertEqual(FakeComfyUIHandler.requests, [("GET", "/object_info")])
            finally:
                app_server.shutdown()
                app_server.server_close()
                app_thread.join(timeout=2)

    def test_local_generation_submits_polls_and_downloads_only_standard_graph_output(self):
        checkpoints = []
        image, metadata = generate_local_txt2img(
            {"comfyui_base_url": self.base_url}, model="model-a.safetensors",
            prompt="A paper boat on a pond", negative_prompt="text", seed=42,
            width=512, height=512, steps=20, cfg=7.0, timeout=1, poll_interval=0.01,
            on_submitting=lambda: checkpoints.append("submitting"),
            on_submitted=lambda prompt_id: checkpoints.append(prompt_id))
        self.assertEqual(checkpoints, ["submitting", "test-prompt-1"])
        self.assertEqual(image, FakeComfyUIHandler.png)
        self.assertEqual(metadata["prompt_id"], "test-prompt-1")
        self.assertEqual(metadata["sampler"], "euler")
        self.assertEqual(metadata["scheduler"], "normal")
        self.assertEqual([path for method, path in FakeComfyUIHandler.requests if method == "POST"], ["/prompt"])
        workflow = FakeComfyUIHandler.submitted_workflow["prompt"]
        self.assertEqual(workflow["1"]["inputs"]["ckpt_name"], "model-a.safetensors")
        self.assertEqual(workflow["2"]["inputs"]["text"], "A paper boat on a pond")
        self.assertNotIn("AgnesImage", {node["class_type"] for node in workflow.values()})

    def test_local_generation_resume_does_not_submit_a_second_workflow(self):
        image, metadata = generate_local_txt2img(
            {"comfyui_base_url": self.base_url}, model="model-a.safetensors",
            prompt="A paper boat on a pond", negative_prompt="", seed=42,
            width=512, height=512, steps=20, cfg=7.0, resume_prompt_id="test-prompt-1",
            timeout=1, poll_interval=0.01)
        self.assertEqual(image, FakeComfyUIHandler.png)
        self.assertEqual(metadata["prompt_id"], "test-prompt-1")
        self.assertFalse(any(method == "POST" and path == "/prompt"
                             for method, path in FakeComfyUIHandler.requests))

    def test_local_generation_cancel_removes_pending_prompt_without_cloud_fallback(self):
        FakeComfyUIHandler.cancel_queued = True
        cancel_checks = iter((False, False, True))
        with self.assertRaises(JobCancelled):
            generate_local_txt2img(
                {"comfyui_base_url": self.base_url}, model="model-a.safetensors",
                prompt="A paper boat on a pond", negative_prompt="", seed=42,
                width=512, height=512, steps=20, cfg=7.0,
                cancel_requested=lambda: next(cancel_checks, True), timeout=1, poll_interval=0.01)
        self.assertEqual([path for method, path in FakeComfyUIHandler.requests if method == "POST"],
                         ["/prompt", "/queue"])
        self.assertFalse(any("agnes" in path.lower() or "api.openai" in path.lower()
                             for _, path in FakeComfyUIHandler.requests))

    def test_settings_save_only_loopback_comfyui_address(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch("factory.settings.SETTINGS_PATH", Path(tmp) / "settings.json"), \
             patch("factory.settings.ENV_PATH", Path(tmp) / "missing.env"):
            saved = save_settings({"comfyui_base_url": self.base_url,
                                   "comfyui_local_model": "model-a.safetensors"})
            self.assertEqual(saved["comfyui_base_url"], self.base_url)
            self.assertEqual(saved["comfyui_local_model"], "model-a.safetensors")
            persisted = json.loads((Path(tmp) / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(persisted["comfyui_base_url"], self.base_url)
            self.assertEqual(persisted["comfyui_local_model"], "model-a.safetensors")
            with self.assertRaises(ComfyUIError):
                save_settings({"comfyui_base_url": "http://example.com:8188"})

    def test_local_server_api_returns_discovery_and_does_not_run_workflow(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch("factory.server.SETTINGS_PATH", Path(tmp) / "settings.json"), \
             patch("factory.settings.SETTINGS_PATH", Path(tmp) / "settings.json"), \
             patch("factory.settings.ENV_PATH", Path(tmp) / "missing.env"):
            app_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            app_thread = Thread(target=app_server.serve_forever, daemon=True)
            app_thread.start()
            try:
                request = Request(f"http://127.0.0.1:{app_server.server_port}/api/settings/comfyui/test",
                                  data=json.dumps({"base_url": self.base_url}).encode("utf-8"),
                                  headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(request) as response:
                    result = json.loads(response.read())
                self.assertTrue(result["connected"])
                self.assertTrue(result["nodes"]["AgnesImage"])
                self.assertEqual(FakeComfyUIHandler.requests, [("GET", "/system_stats"), ("GET", "/object_info")])

                bad_request = Request(f"http://127.0.0.1:{app_server.server_port}/api/settings/comfyui/test",
                                      data=b'{"base_url":"http://example.com"}',
                                      headers={"Content-Type": "application/json"}, method="POST")
                with self.assertRaises(HTTPError) as error:
                    urlopen(bad_request)
                self.assertEqual(error.exception.code, 400)
            finally:
                app_server.shutdown()
                app_server.server_close()
                app_thread.join(timeout=2)


    def test_agnes_profile_endpoint_and_graph_build(self):
        from factory.comfyui_profiles import (AGNES_PROFILE_ID, WorkflowProfileError,
                                              build_agnes_txt2img_workflow, inspect_agnes_profile)
        with patch("factory.server.load_settings", return_value={"comfyui_base_url": self.base_url}):
            app_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            app_thread = Thread(target=app_server.serve_forever, daemon=True)
            app_thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{app_server.server_port}/api/settings/comfyui/agnes-profile") as response:
                    result = json.loads(response.read())
                self.assertEqual(result["profile_id"], AGNES_PROFILE_ID)
                self.assertTrue(result["available"])
                self.assertEqual(result["quality"], ["1K", "2K", "3K", "4K"])
                self.assertEqual(result["text_preset"], "Prompt Enhance")
            finally:
                app_server.shutdown()
                app_server.server_close()
                app_thread.join(timeout=2)
        object_info = json.loads(urlopen(self.base_url + "/object_info").read())
        built = build_agnes_txt2img_workflow(
            object_info, prompt="Тёплая мастерская", quality="1K", aspect_ratio="4:3",
            seed=42, preprocess_prompt=True)
        graph = built["prompt"]
        self.assertEqual(set(graph), {"13", "14", "3"})
        self.assertEqual(graph["13"]["inputs"]["prompt"], ["14", 0])
        self.assertEqual(graph["14"]["inputs"]["preset"], "Prompt Enhance")
        self.assertEqual(graph["3"]["inputs"]["images"], ["13", 0])
        plain = build_agnes_txt2img_workflow(
            object_info, prompt="Тёплая мастерская", quality="2K", aspect_ratio="16:9",
            seed=7, preprocess_prompt=False)
        self.assertNotIn("14", plain["prompt"])
        self.assertEqual(plain["prompt"]["13"]["inputs"]["prompt"], "Тёплая мастерская")
        with self.assertRaises(WorkflowProfileError):
            build_agnes_txt2img_workflow(object_info, prompt="x", quality="8K",
                                         aspect_ratio="4:3", seed=1)
        with self.assertRaises(WorkflowProfileError):
            build_agnes_txt2img_workflow(object_info, prompt="x", quality="1K",
                                         aspect_ratio="4:3", seed=1, text_preset="Нет такого")
        no_text = dict(object_info)
        del no_text["AgnesText"]
        missing = inspect_agnes_profile(no_text)
        self.assertFalse(missing["available"])
        self.assertEqual(missing["missing_nodes"], ["AgnesText"])
        with self.assertRaises(WorkflowProfileError):
            build_agnes_txt2img_workflow(no_text, prompt="x", quality="1K",
                                         aspect_ratio="4:3", seed=1, preprocess_prompt=True)

    def test_agnes_generate_success_downloads_temp_image(self):
        FakeComfyUIHandler.agnes_mode = True
        data, metadata = generate_agnes_txt2img(
            {"comfyui_base_url": self.base_url}, prompt="Тёплая мастерская", quality="1K",
            aspect_ratio="4:3", seed=42, preprocess_prompt=True, timeout=1, poll_interval=0.01)
        self.assertEqual(data, FakeComfyUIHandler.png)
        self.assertEqual(metadata["profile_id"], "comfyui-agnes-t2i-v1")
        self.assertEqual(metadata["text_preset"], "Prompt Enhance")
        graph = FakeComfyUIHandler.submitted_workflow["prompt"]
        self.assertEqual(graph["14"]["inputs"]["preset"], "Prompt Enhance")
        self.assertTrue(any("type=temp" in path for method, path in FakeComfyUIHandler.requests
                            if method == "GET" and path.startswith("/view?")))

    def test_agnes_generate_without_preprocess_has_no_text_node(self):
        FakeComfyUIHandler.agnes_mode = True
        data, metadata = generate_agnes_txt2img(
            {"comfyui_base_url": self.base_url}, prompt="Тёплая мастерская", quality="1K",
            aspect_ratio="4:3", seed=42, preprocess_prompt=False, timeout=1, poll_interval=0.01)
        self.assertIsNone(metadata["text_preset"])
        graph = FakeComfyUIHandler.submitted_workflow["prompt"]
        self.assertNotIn("14", graph)
        self.assertEqual(graph["13"]["inputs"]["prompt"], "Тёплая мастерская")


    def test_agnes_generate_cancel_queued_deletes_prompt(self):
        FakeComfyUIHandler.agnes_mode = True
        FakeComfyUIHandler.cancel_queued = True
        cancel_checks = iter((False, False, True))
        with self.assertRaises(JobCancelled):
            generate_agnes_txt2img(
                {"comfyui_base_url": self.base_url}, prompt="Тёплая мастерская", quality="1K",
                aspect_ratio="4:3", seed=42, preprocess_prompt=True,
                cancel_requested=lambda: next(cancel_checks, True), timeout=1, poll_interval=0.01)
        self.assertEqual([path for method, path in FakeComfyUIHandler.requests if method == "POST"],
                         ["/prompt", "/queue"])

    def test_agnes_generate_rejected_by_local_node_validation(self):
        FakeComfyUIHandler.agnes_mode = True
        FakeComfyUIHandler.node_errors = True
        with self.assertRaisesRegex(ComfyUIError, "отклонил Agnes-граф"):
            generate_agnes_txt2img(
                {"comfyui_base_url": self.base_url}, prompt="Тёплая мастерская", quality="1K",
                aspect_ratio="4:3", seed=42, preprocess_prompt=True, timeout=1, poll_interval=0.01)

    def test_agnes_profile_connection_is_read_only(self):
        result = inspect_agnes_connection({"comfyui_base_url": self.base_url})
        self.assertTrue(result["available"])
        self.assertEqual(FakeComfyUIHandler.requests, [("GET", "/object_info")])

    def test_settings_save_agnes_profile_keys(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch("factory.settings.SETTINGS_PATH", Path(tmp) / "settings.json"), \
             patch("factory.settings.ENV_PATH", Path(tmp) / "missing.env"):
            saved = save_settings({"comfyui_image_profile": "agnes", "comfyui_agnes_quality": "2K",
                                  "comfyui_agnes_aspect_ratio": "16:9",
                                  "comfyui_agnes_preprocess_prompt": False})
            self.assertEqual(saved["comfyui_image_profile"], "agnes")
            self.assertEqual(saved["comfyui_agnes_quality"], "2K")
            self.assertEqual(saved["comfyui_agnes_aspect_ratio"], "16:9")
            self.assertFalse(saved["comfyui_agnes_preprocess_prompt"])
            with self.assertRaises(ValueError):
                save_settings({"comfyui_image_profile": "remote"})


if __name__ == "__main__":
    unittest.main()
