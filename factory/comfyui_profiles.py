"""Validated, versioned local ComfyUI workflow profiles.

Profiles are assembled from the live /object_info schema. This module builds workflow JSON
only; callers decide when to submit it, and no function here performs an API request.
"""
from __future__ import annotations

from typing import Any


PROFILE_ID = "comfyui-core-txt2img-v1"

_REQUIRED_NODES = (
    "CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler",
    "VAEDecode", "SaveImage",
)


class WorkflowProfileError(ValueError):
    pass


def _node_info(object_info: dict, class_type: str) -> dict:
    value = object_info.get(class_type)
    if not isinstance(value, dict):
        raise WorkflowProfileError(f"Не найдена обязательная нода {class_type}")
    return value


def _input_def(node: dict, name: str) -> list:
    inputs = node.get("input", {})
    for group in ("required", "optional"):
        values = inputs.get(group, {}) if isinstance(inputs, dict) else {}
        if name in values:
            definition = values[name]
            if isinstance(definition, list) and definition:
                return definition
            raise WorkflowProfileError(f"Некорректная схема input {name}")
    raise WorkflowProfileError(f"Нода {node.get('name', 'ComfyUI')} не содержит input {name}")


def _choices(node: dict, name: str) -> list[str] | None:
    definition = _input_def(node, name)
    options = definition[0]
    if isinstance(options, list):
        return [str(item) for item in options]
    return None


def _output_index(node: dict, name: str) -> int:
    names = node.get("output_name")
    outputs = node.get("output")
    if not isinstance(names, list) or not isinstance(outputs, list):
        raise WorkflowProfileError(f"В схеме {node.get('name', 'ComfyUI')} нет output_name/output")
    for index, output_name in enumerate(names):
        if str(output_name).upper() == name.upper() and index < len(outputs):
            return index
    raise WorkflowProfileError(f"У ноды {node.get('name', 'ComfyUI')} нет выхода {name}")


def inspect_local_txt2img_profile(object_info: dict) -> dict:
    """Return usable model/sampler/scheduler options only when the core profile is present."""
    if not isinstance(object_info, dict):
        raise WorkflowProfileError("/object_info должен содержать JSON-объект")
    nodes = {name: _node_info(object_info, name) for name in _REQUIRED_NODES}
    required_inputs = {
        "CheckpointLoaderSimple": ("ckpt_name",),
        "CLIPTextEncode": ("text", "clip"),
        "EmptyLatentImage": ("width", "height", "batch_size"),
        "KSampler": ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise",
                     "model", "positive", "negative", "latent_image"),
        "VAEDecode": ("samples", "vae"),
        "SaveImage": ("images", "filename_prefix"),
    }
    for class_type, names in required_inputs.items():
        for name in names:
            _input_def(nodes[class_type], name)
    checkpoints = _choices(nodes["CheckpointLoaderSimple"], "ckpt_name") or []
    samplers = _choices(nodes["KSampler"], "sampler_name") or []
    schedulers = _choices(nodes["KSampler"], "scheduler") or []
    if not checkpoints:
        raise WorkflowProfileError("ComfyUI не сообщил доступные checkpoint-модели")
    if not samplers or not schedulers:
        raise WorkflowProfileError("ComfyUI не сообщил варианты sampler/scheduler")
    return {"profile_id": PROFILE_ID, "available": True,
            "models": checkpoints[:500], "samplers": samplers[:100], "schedulers": schedulers[:100]}


def _bounded_number(node: dict, name: str, value: int | float) -> int | float:
    definition = _input_def(node, name)
    metadata = definition[1] if len(definition) > 1 and isinstance(definition[1], dict) else {}
    try:
        minimum = float(metadata.get("min", value))
        maximum = float(metadata.get("max", value))
    except (TypeError, ValueError):
        minimum, maximum = value, value
    if not minimum <= float(value) <= maximum:
        raise WorkflowProfileError(f"Значение {name} выходит за пределы ComfyUI")
    return value


def _scalar_default(definition: list, *, name: str) -> Any:
    options, metadata = definition[0], definition[1] if len(definition) > 1 and isinstance(definition[1], dict) else {}
    if name == "control_after_generate" and isinstance(options, list) and "fixed" in options:
        return "fixed"
    if "default" in metadata:
        return metadata["default"]
    raise WorkflowProfileError(f"У профиля нет безопасного значения для обязательного input {name}")


def build_local_txt2img_workflow(object_info: dict, *, model: str, prompt: str,
                                 negative_prompt: str = "", seed: int = 0,
                                 width: int = 512, height: int = 512,
                                 steps: int = 20, cfg: float = 7.0) -> dict:
    """Build a core text-to-image graph after validating it against live node metadata."""
    inspect_local_txt2img_profile(object_info)
    model_node = _node_info(object_info, "CheckpointLoaderSimple")
    clip_node = _node_info(object_info, "CLIPTextEncode")
    latent_node = _node_info(object_info, "EmptyLatentImage")
    sampler_node = _node_info(object_info, "KSampler")
    decode_node = _node_info(object_info, "VAEDecode")
    save_node = _node_info(object_info, "SaveImage")
    if model not in (_choices(model_node, "ckpt_name") or []):
        raise WorkflowProfileError("Выбранная checkpoint-модель отсутствует в локальном ComfyUI")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
        raise WorkflowProfileError("Для локальной генерации укажите prompt длиной до 4000 символов")
    if not isinstance(negative_prompt, str) or len(negative_prompt) > 4000:
        raise WorkflowProfileError("Negative prompt не должен превышать 4000 символов")
    if type(seed) is not int or seed < 0 or seed > 0xFFFFFFFFFFFFFFFF:
        raise WorkflowProfileError("Seed должен быть целым числом от 0 до 2^64−1")
    if (type(width) is not int or type(height) is not int or width < 64 or height < 64
            or width > 8192 or height > 8192 or width * height > 40_000_000
            or width % 8 or height % 8):
        raise WorkflowProfileError("Размер изображения должен быть от 64 px, кратен 8 и не превышать лимит 40 Мп")
    if type(steps) is not int or not 1 <= steps <= 100:
        raise WorkflowProfileError("Число шагов должно быть от 1 до 100")
    if type(cfg) not in (int, float) or not 0 <= float(cfg) <= 30:
        raise WorkflowProfileError("CFG должен быть от 0 до 30")

    sampler_choices = _choices(sampler_node, "sampler_name") or []
    scheduler_choices = _choices(sampler_node, "scheduler") or []
    if "euler" in sampler_choices:
        sampler_name = "euler"
    else:
        sampler_name = sampler_choices[0]
    scheduler = "normal" if "normal" in scheduler_choices else scheduler_choices[0]

    model_outputs = {name.upper(): _output_index(model_node, name) for name in ("MODEL", "CLIP", "VAE")}
    clip_output = _output_index(clip_node, "CONDITIONING")
    latent_output = _output_index(latent_node, "LATENT")
    sampler_outputs = _output_index(sampler_node, "LATENT")
    decode_output = _output_index(decode_node, "IMAGE")
    for name in ("samples", "vae"):
        _input_def(decode_node, name)
    for name in ("images", "filename_prefix"):
        _input_def(save_node, name)

    graph: dict[str, dict] = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt.strip(), "clip": ["1", model_outputs["CLIP"]]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt.strip(), "clip": ["1", model_outputs["CLIP"]]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", model_outputs["MODEL"]], "positive": ["2", clip_output],
            "negative": ["3", clip_output], "latent_image": ["4", latent_output],
            "seed": seed, "steps": steps, "cfg": float(cfg), "sampler_name": sampler_name,
            "scheduler": scheduler, "denoise": 1.0,
        }},
        "6": {"class_type": "VAEDecode", "inputs": {
            "samples": ["5", sampler_outputs], "vae": ["1", model_outputs["VAE"]]}},
        "7": {"class_type": "SaveImage", "inputs": {
            "images": ["6", decode_output], "filename_prefix": "ai_video_factory"}},
    }

    # Fill newly-added mandatory scalar controls only when /object_info defines a default
    # or a specifically safe deterministic value. Unknown required inputs fail closed.
    links = {
        "CheckpointLoaderSimple": graph["1"]["inputs"],
        "CLIPTextEncode": graph["2"]["inputs"],
        "EmptyLatentImage": graph["4"]["inputs"],
        "KSampler": graph["5"]["inputs"],
        "VAEDecode": graph["6"]["inputs"],
        "SaveImage": graph["7"]["inputs"],
    }
    for class_type, node in (("CheckpointLoaderSimple", model_node), ("CLIPTextEncode", clip_node),
                             ("EmptyLatentImage", latent_node), ("KSampler", sampler_node),
                             ("VAEDecode", decode_node), ("SaveImage", save_node)):
        required = node.get("input", {}).get("required", {})
        for name, definition in required.items():
            if name in links[class_type]:
                continue
            if name in ("seed", "steps", "cfg", "width", "height", "batch_size", "denoise"):
                continue
            links[class_type][name] = _scalar_default(definition, name=name)

    for name, value in (("width", width), ("height", height), ("batch_size", 1)):
        _bounded_number(latent_node, name, value)
    for name, value in (("steps", steps), ("cfg", cfg), ("seed", seed), ("denoise", 1.0)):
        _bounded_number(sampler_node, name, value)
    return {"profile_id": PROFILE_ID, "prompt": graph}
