import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory.comfyui_profiles import (PROFILE_ID, WorkflowProfileError,
                                       build_local_txt2img_workflow,
                                       inspect_local_txt2img_profile)


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


if __name__ == "__main__":
    unittest.main()
