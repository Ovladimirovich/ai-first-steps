import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from unittest.mock import patch

from factory.comfyui import ComfyUIError, generate_agnes_image
from factory.comfyui_profiles import (AGNES_IMAGE_PROFILE_ID, PROFILE_ID, WorkflowProfileError,
                                       build_agnes_image_workflow, build_local_txt2img_workflow,
                                       inspect_agnes_image_profile, inspect_local_txt2img_profile)
from factory.jobs import JobCancelled


def field(kind, **metadata):
    return [kind, metadata]


def fake_object_info(extra_sampler_input=False):
    sampler_inputs = {
        "seed": field("INT", min=0, max=0xFFFFFFFFFFFFFFFF),
        "steps": field("INT", min=1, max=100),
        "cfg": field("FLOAT", min=0.0, max=30.0),
        "sampler_name": field(["euler", "dpmpp_2m"]),
        "scheduler": field(["normal", "karras"]),
        "denoise": field("FLOAT", min=0.0, max=1.0),
        "model": field("MODEL"),
        "positive": field("CONDITIONING"),
        "negative": field("CONDITIONING"),
        "latent_image": field("LATENT"),
        "control_after_generate": field(["fixed", "randomize"]),
    }
    if extra_sampler_input:
        sampler_inputs["unmapped_required_link"] = field("CUSTOM_TYPE")
    return {
        "CheckpointLoaderSimple": {
            "input": {"required": {"ckpt_name": field(["model-a.safetensors", "model-b.safetensors"])}},
            "output": ["MODEL", "CLIP", "VAE"], "output_name": ["MODEL", "CLIP", "VAE"],
        },
        "CLIPTextEncode": {
            "input": {"required": {"text": field("STRING"), "clip": field("CLIP")}},
            "output": ["CONDITIONING"], "output_name": ["CONDITIONING"],
        },
        "EmptyLatentImage": {
            "input": {"required": {"width": field("INT", min=64, max=8192),
                                    "height": field("INT", min=64, max=8192),
                                    "batch_size": field("INT", min=1, max=64)}},
            "output": ["LATENT"], "output_name": ["LATENT"],
        },
        "KSampler": {"input": {"required": sampler_inputs},
                     "output": ["LATENT"], "output_name": ["LATENT"]},
        "VAEDecode": {"input": {"required": {"samples": field("LATENT"), "vae": field("VAE")}},
                      "output": ["IMAGE"], "output_name": ["IMAGE"]},
        "SaveImage": {"input": {"required": {"images": field("IMAGE"), "filename_prefix": field("STRING")}}},
    }


def fake_agnes_object_info():
    return {
        "AgnesImage": {
            "input": {"required": {
                "prompt": field("STRING", default="", multiline=True),
                "quality": field("COMBO", default="1K", options=["1K", "2K", "3K", "4K"]),
                "aspect_ratio": field("COMBO", default="auto", options=[
                    "auto", "1:1", "2:3", "3:4", "4:5", "9:16", "9:21",
                    "3:2", "4:3", "5:4", "16:9", "21:9"]),
                "seed": field("INT", min=0, max=0xFFFFFFFFFFFFFFFF),
            }, "optional": {"images": field("COMFY_AUTOGROW_V3", template="image_0..image_4", min=0, max=4)}},
            "output": ["IMAGE"], "output_name": ["images"],
        },
        "PreviewImage": {"input": {"required": {"images": field("IMAGE")},
                                    "hidden": {"prompt": field("PROMPT"),
                                               "extra_pnginfo": field("EXTRA_PNGINFO")}},
                         "output": ["IMAGE"], "output_name": ["images"], "output_node": True},
        "AgnesText": {},
    }


class LocalComfyUIProfileTests(unittest.TestCase):
    def test_profile_inspection_reports_models_and_sampler_choices(self):
        result = inspect_local_txt2img_profile(fake_object_info())
        self.assertEqual(result["profile_id"], PROFILE_ID)
        self.assertTrue(result["available"])
        self.assertEqual(result["models"], ["model-a.safetensors", "model-b.safetensors"])
        self.assertEqual(result["samplers"], ["euler", "dpmpp_2m"])
        self.assertEqual(result["schedulers"], ["normal", "karras"])

    def test_builder_uses_live_output_indices_and_validates_selected_options(self):
        info = fake_object_info()
        info["CheckpointLoaderSimple"]["output_name"] = ["VAE", "CLIP", "MODEL"]
        result = build_local_txt2img_workflow(
            info, model="model-b.safetensors", prompt="A paper boat on a pond", negative_prompt="text",
            seed=123, width=640, height=512, steps=24, cfg=6.5)
        graph = result["prompt"]
        self.assertEqual(result["profile_id"], PROFILE_ID)
        self.assertEqual(graph["1"]["inputs"]["ckpt_name"], "model-b.safetensors")
        self.assertEqual(graph["2"]["inputs"]["clip"], ["1", 1])
        self.assertEqual(graph["5"]["inputs"]["model"], ["1", 2])
        self.assertEqual(graph["5"]["inputs"]["sampler_name"], "euler")
        self.assertEqual(graph["5"]["inputs"]["control_after_generate"], "fixed")
        self.assertEqual(graph["7"]["inputs"]["images"], ["6", 0])
        with self.assertRaisesRegex(WorkflowProfileError, "отсутствует"):
            build_local_txt2img_workflow(info, model="missing.safetensors", prompt="Valid prompt")

    def test_builder_rejects_missing_nodes_unknown_required_fields_and_unsafe_bounds(self):
        with self.assertRaisesRegex(WorkflowProfileError, "Не найдена"):
            inspect_local_txt2img_profile({})
        with self.assertRaisesRegex(WorkflowProfileError, "безопасного значения"):
            build_local_txt2img_workflow(fake_object_info(extra_sampler_input=True),
                                         model="model-a.safetensors", prompt="A valid prompt")
        info = fake_object_info()
        with self.assertRaisesRegex(WorkflowProfileError, "40 Мп"):
            build_local_txt2img_workflow(info, model="model-a.safetensors", prompt="A valid prompt",
                                         width=8192, height=8192)
        with self.assertRaisesRegex(WorkflowProfileError, "до 4000"):
            build_local_txt2img_workflow(info, model="model-a.safetensors", prompt="x" * 4001)

    def test_agnes_image_profile_builds_only_text_to_image_branch_from_live_schema(self):
        info = fake_agnes_object_info()
        profile = inspect_agnes_image_profile(info)
        self.assertEqual(profile["profile_id"], AGNES_IMAGE_PROFILE_ID)
        self.assertEqual(profile["quality_options"], ["1K", "2K", "3K", "4K"])
        self.assertFalse(profile["supports_negative_prompt"])
        built = build_agnes_image_workflow(
            info, prompt="Бирюзовый робот-кубик и школьница", seed=4267882469,
            quality="1K", aspect_ratio="16:9")
        self.assertEqual(built["profile_id"], AGNES_IMAGE_PROFILE_ID)
        self.assertEqual(built["output_node_id"], "3")
        self.assertEqual(built["prompt"]["13"]["class_type"], "AgnesImage")
        self.assertEqual(built["prompt"]["13"]["inputs"], {
            "prompt": "Бирюзовый робот-кубик и школьница", "quality": "1K",
            "aspect_ratio": "16:9", "seed": 4267882469})
        self.assertEqual(built["prompt"]["3"], {
            "class_type": "PreviewImage", "inputs": {
                "images": ["13", 0], "prompt": None, "extra_pnginfo": None}})
        self.assertNotIn("AgnesText", {node["class_type"] for node in built["prompt"].values()})

    def test_agnes_image_profile_rejects_schema_mismatch_and_unsafe_parameters(self):
        info = fake_agnes_object_info()
        with self.assertRaisesRegex(WorkflowProfileError, "[Нн]е найдена"):
            inspect_agnes_image_profile({"AgnesText": {}})
        with self.assertRaisesRegex(WorkflowProfileError, "соотношение сторон"):
            build_agnes_image_workflow(info, prompt="A valid image", seed=1, aspect_ratio="2:1")
        with self.assertRaisesRegex(WorkflowProfileError, "длиной"):
            build_agnes_image_workflow(info, prompt="", seed=1)
        with self.assertRaisesRegex(WorkflowProfileError, "Seed"):
            build_agnes_image_workflow(info, prompt="A valid image", seed=-1)


class AgnesImageExecutionTests(unittest.TestCase):
    def test_runtime_guard_blocks_before_even_reading_comfyui_schema(self):
        with patch("factory.comfyui._get_json") as get_mock:
            with self.assertRaisesRegex(ComfyUIError, "выключен"):
                generate_agnes_image({"comfyui_base_url": "http://127.0.0.1:8188"},
                                     prompt="A blue robot", seed=11)
        get_mock.assert_not_called()

    def test_submits_exactly_one_api_graph_then_fetches_one_output(self):
        history = {"prompt-42": {"status": {"status_str": "success", "completed": True},
                                 "outputs": {"3": {"images": [{"filename": "agnes.png", "type": "output"}]}}}}
        get_json = {"AgnesImage": fake_agnes_object_info()["AgnesImage"],
                    "PreviewImage": fake_agnes_object_info()["PreviewImage"]}
        with (
            patch("factory.comfyui._get_json", side_effect=[get_json, history]) as get_mock,
            patch("factory.comfyui._post_json", return_value={"prompt_id": "prompt-42"}) as post_mock,
            patch("factory.comfyui._get_bytes", return_value=b"png-bytes") as bytes_mock,
            patch("factory.comfyui.time.sleep"),
            patch("factory.pipeline.AGNES_IMAGE_RUNTIME_ENABLED", True),
        ):
            submitted, accepted = [], []
            image, metadata = generate_agnes_image(
                {"comfyui_base_url": "http://127.0.0.1:8188"}, prompt="A blue robot",
                seed=11, quality="1K", aspect_ratio="16:9",
                on_submitting=lambda: submitted.append(True),
                on_submitted=accepted.append)
        self.assertEqual(image, b"png-bytes")
        self.assertEqual(post_mock.call_count, 1)
        self.assertEqual(submitted, [True])
        self.assertEqual(accepted, ["prompt-42"])
        self.assertEqual(metadata["prompt_id"], "prompt-42")
        self.assertEqual(post_mock.call_args.args[1], "/prompt")
        self.assertEqual(post_mock.call_args.args[2]["prompt"]["13"]["class_type"], "AgnesImage")
        self.assertEqual(bytes_mock.call_count, 1)
        self.assertEqual(get_mock.call_count, 2)

    def test_cancel_before_submission_sends_nothing(self):
        with (
            patch("factory.comfyui._get_json", return_value=fake_agnes_object_info()),
            patch("factory.comfyui._post_json") as post_mock,
            patch("factory.pipeline.AGNES_IMAGE_RUNTIME_ENABLED", True),
        ):
            with self.assertRaises(JobCancelled):
                generate_agnes_image({"comfyui_base_url": "http://127.0.0.1:8188"},
                                     prompt="A blue robot", seed=11,
                                     cancel_requested=lambda: True)
        post_mock.assert_not_called()

    def test_resume_uses_saved_prompt_id_without_resubmission(self):
        history = {"prompt-42": {"status": {"status_str": "success", "completed": True},
                                 "outputs": {"3": {"images": [{"filename": "agnes.png"}]}}}}
        with (
            patch("factory.comfyui._get_json", side_effect=[fake_agnes_object_info(), history]),
            patch("factory.comfyui._post_json") as post_mock,
            patch("factory.comfyui._get_bytes", return_value=b"png-bytes"),
            patch("factory.comfyui.time.sleep"),
            patch("factory.pipeline.AGNES_IMAGE_RUNTIME_ENABLED", True),
        ):
            image, metadata = generate_agnes_image(
                {"comfyui_base_url": "http://127.0.0.1:8188"}, prompt="A blue robot", seed=11,
                resume_prompt_id="prompt-42")
        self.assertEqual(image, b"png-bytes")
        self.assertEqual(metadata["prompt_id"], "prompt-42")
        post_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
