"""Тайминг фабрики: сохраняет проверенные правила реального легаси-конвейера."""

TIMING_ENGINE_VERSION = "factory-timing-v1"


def pause_after_s(line: dict) -> float:
    text = str(line.get("text", "")).strip()
    pause = float(line["pause_after_s"]) if line.get("pause_after_s") is not None else (0.55 if len(text) > 65 else 0.42)
    if text.startswith(("Проверка!", "ИИ сделает")):
        pause = 4.2
    return pause


def timing_for(spec: dict, duration_overrides: dict[str, float] | None = None) -> dict:
    rows = []
    cursor = 0.0
    previous_scene = None
    overrides = duration_overrides or {}
    scenes = sorted(spec.get("script", {}).get("scenes", []), key=lambda x: x.get("order", 0))
    for scene in scenes:
        if previous_scene is not None and scene["id"] != previous_scene:
            cursor += 1.1
        for line in scene.get("lines", []):
            text = line["text"].strip()
            duration = float(overrides.get(line["id"], max(1.45, len(text) / 10.81)))
            start = cursor
            end = start + duration
            rows.append({"id": line["id"], "scene": scene["id"], "hero": line["hero"],
                         "text": text, "start": round(start, 3), "end": round(end, 3), "dur": round(duration, 3)})
            cursor = end + pause_after_s(line)
        previous_scene = scene["id"]
    return {"fps": int(spec.get("format", {}).get("fps", 30)), "total": round(cursor, 2), "lines": rows, "cues": []}
