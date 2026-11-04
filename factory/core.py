from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from .timing import timing_for

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / ".factory" / "projects"
RENDERER_VERSION = "factory-ffmpeg-segments-v3"
DEFAULT_HEROES = [
    {"id": "h1", "name": "Бит", "role": "explains", "about": "добрый робот-кубик", "look": "бирюзовый кубик", "voice": {"provider": "demo", "voice_id": "male-warm", "rate": 1.0}},
    {"id": "h2", "name": "Маша", "role": "asks", "about": "любознательная школьница", "look": "худи и рюкзак", "voice": {"provider": "demo", "voice_id": "female-young", "rate": 1.0}},
]
PALETTES = {
    "warm_workshop": {"bg": "#FFF6E0", "ink": "#1B2A4A", "accent": "#2EE6D6", "highlight": "#FFD23F"},
    "bright_clouds": {"bg": "#EAF7FF", "ink": "#1B2A4A", "accent": "#52C7EA", "highlight": "#FFD23F"},
    "night_space": {"bg": "#18233D", "ink": "#FFFFFF", "accent": "#8A7DFF", "highlight": "#FFD23F"},
}


def new_spec(theme="", audience="Дети 11–14 лет", duration=60, style="warm_workshop"):
    return {
        "spec_version": 1,
        "intent": {"theme": theme, "audience": {"preset": "kids_11_14", "note": audience},
                   "target_duration_s": int(duration), "tone": "дружелюбно, с лёгким юмором", "language": "ru"},
        "heroes": json.loads(json.dumps(DEFAULT_HEROES, ensure_ascii=False)),
        "look": {"style_preset": style, "palette": PALETTES.get(style, PALETTES["warm_workshop"]), "reference_image": None},
        "format": {"width": 1920, "height": 1080, "fps": 30, "captions": "burned"},
        "timing_policy": {"preset": "legacy_v1"},
        "script": {"generator": {"provider": "demo", "version": "rule-v1"}, "scenes": []},
    }


def safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "", value)


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def project_dir(project_id: str) -> Path:
    return DATA_ROOT / safe_id(project_id)


def load_project(project_id: str) -> dict:
    directory = project_dir(project_id)
    path = directory / "project.json"
    if not path.exists():
        raise FileNotFoundError(project_id)
    project = json.loads(path.read_text(encoding="utf-8"))
    project["spec"] = json.loads((directory / "spec.json").read_text(encoding="utf-8"))
    return project


def save_project(project: dict) -> None:
    directory = project_dir(project["id"])
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "spec.json").write_text(json.dumps(project["spec"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metadata = {k: v for k, v in project.items() if k != "spec"}
    (directory / "project.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_projects() -> list[dict]:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    result = []
    for path in DATA_ROOT.iterdir():
        if path.is_dir() and (path / "project.json").exists():
            try:
                p = load_project(path.name)
                result.append({"id": p["id"], "title": p.get("title", "Новый ролик"), "updated_at": p.get("updated_at"), "revision": p.get("revision", 1)})
            except (ValueError, OSError):
                continue
    return sorted(result, key=lambda x: x.get("updated_at", ""), reverse=True)


def create_project(payload: dict) -> dict:
    theme = str(payload.get("theme", "")).strip()
    duration = int(payload.get("duration", 60))
    if duration not in (30, 45, 60, 90, 120):
        duration = 60
    style = payload.get("style", "warm_workshop")
    if style not in PALETTES:
        style = "warm_workshop"
    project_id = uuid.uuid4().hex[:12]
    spec = new_spec(theme, payload.get("audience", "Дети 11–14 лет"), duration, style)
    project = {"id": project_id, "title": theme[:80] or "Новый ролик", "revision": 1,
               "current_step": 0, "created_at": time.time(), "updated_at": time.time(), "spec": spec}
    save_project(project)
    return project


def draft_script(spec: dict) -> dict:
    """Дешёвый шаблонный черновик, без сетевых вызовов и платных API."""
    theme = (spec.get("intent", {}).get("theme") or "интересная тема").strip().rstrip("?.! ")
    if not theme:
        theme = "интересная тема"
    hero_explains = next((h["id"] for h in spec.get("heroes", []) if h.get("role") == "explains"), "h1")
    hero_asks = next((h["id"] for h in spec.get("heroes", []) if h.get("role") == "asks"), "h2")
    raw = [
        ("hook", f"Почему вообще важно разобраться в теме «{theme}»?", hero_asks, "Удивить и зацепить вопросом"),
        ("hook", f"Отличный вопрос! Сейчас разложим «{theme}» на понятные части.", hero_explains, "Пообещать простое объяснение"),
        ("point", f"Представь: {theme.lower()} — это как маленькая команда, где у каждого есть своя задача.", hero_explains, "Объяснить главную идею через аналогию"),
        ("point", f"А какой пример из жизни поможет это заметить?", hero_asks, "Подключить зрителя к рассуждению"),
        ("point", f"Например, обрати внимание на привычные вещи вокруг: они подскажут ответ.", hero_explains, "Дать применимый пример"),
        ("check", f"Проверка: попробуй объяснить «{theme}» одним предложением.", hero_asks, "Проверить понимание"),
        ("payoff", f"Главное — теперь ты знаешь, с чего начать и что проверить самому.", hero_explains, "Закрепить мысль и дать действие"),
        ("payoff", f"Расскажи об этом кому-нибудь сегодня — и увидимся в новом выпуске!", hero_asks, "Тёплое завершение"),
        ("point", f"Посмотри на ещё один случай: знакомые детали часто подсказывают, что происходит.", hero_explains, "Показать второй пример"),
        ("point", f"Получается, я могу заметить эту идею в обычной жизни?", hero_asks, "Связать объяснение с опытом зрителя"),
        ("point", f"Именно! Сравни два примера и найди, что у них общего.", hero_explains, "Помочь увидеть закономерность"),
        ("point", f"А если ответ не сразу понятен, с чего начать проверку?", hero_asks, "Подсказать способ рассуждения"),
        ("check", f"Мини-проверка: назови главный признак темы «{theme}».", hero_asks, "Закрепить ключевое понятие"),
        ("payoff", f"Ты уже можешь объяснить эту идею своими словами — это и есть первый шаг.", hero_explains, "Подчеркнуть самостоятельное понимание"),
        ("payoff", f"Попробуй найти ещё один пример вокруг себя и поделись им с другом.", hero_asks, "Предложить действие после просмотра"),
        ("payoff", f"Увидимся в следующем выпуске — впереди ещё много любопытных вопросов!", hero_explains, "Завершить выпуск"),
    ]
    duration = int(spec.get("intent", {}).get("target_duration_s", 60))
    if duration <= 30:
        selected = [raw[i] for i in (0, 1, 2, 7)]
        sizes, titles = [2, 1, 1], ["Зацепка", "Главная идея", "Вывод"]
    elif duration <= 45:
        selected = [raw[i] for i in (0, 1, 2, 4, 5, 7)]
        sizes, titles = [2, 2, 2], ["Зацепка", "Разбираемся", "Проверка и вывод"]
    elif duration <= 60:
        selected = raw[:8]
        sizes, titles = [2, 3, 3], ["Зацепка", "Разбираемся", "Проверка и вывод"]
    elif duration <= 90:
        selected = raw[:12]
        sizes, titles = [2, 4, 3, 3], ["Зацепка", "Идея и примеры", "Проверяем понимание", "Вывод"]
    else:
        selected = raw[:16]
        sizes, titles = [3, 5, 4, 4], ["Зацепка", "Идея и примеры", "Проверяем понимание", "Вывод"]
    purposes = ["hook", "point", "check", "payoff"]
    goals = ["Заинтересовать зрителя", "Объяснить идею на примерах", "Проверить понимание", "Закрепить мысль и дать действие"]
    scene_defs = []
    start = 0
    for i, size in enumerate(sizes):
        if start >= len(selected):
            break
        scene_defs.append((f"s{i+1}", titles[i], purposes[min(i, len(purposes)-1)], goals[min(i, len(goals)-1)], selected[start:start+size]))
        start += size
    scenes = []
    line_no = 1
    for sid, title, purpose, goal, items in scene_defs:
        lines = []
        for _, text, hero, _ in items:
            lines.append({"id": f"l{line_no}", "hero": hero, "text": text, "pause_after_s": None})
            line_no += 1
        scenes.append({"id": sid, "order": len(scenes) + 1, "title": title, "purpose": purpose,
                       "goal": goal, "visual_note": f"{title}: выразительная карточка и детали по теме «{theme}»",
                       "image": {"mode": "style", "path": None}, "lines": lines})
    spec["script"] = {"generator": {"provider": "demo", "version": "rule-v1"}, "scenes": scenes}
    return spec


def validate_spec(spec: dict) -> None:
    if spec.get("spec_version") != 1:
        raise ValueError("Поддерживается только версия спецификации 1")
    intent = spec.get("intent", {})
    if not str(intent.get("theme", "")).strip():
        raise ValueError("Сначала укажите тему ролика")
    if not spec.get("heroes"):
        raise ValueError("Добавьте хотя бы одного героя")
    ids = {h["id"] for h in spec["heroes"]}
    if any(not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", value) or value in (".", "..") for value in ids):
        raise ValueError("ID героя содержит недопустимые символы")
    line_ids = set()
    scene_ids = set()
    for scene in spec.get("script", {}).get("scenes", []):
        scene_id = str(scene.get("id", ""))
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", scene_id) or scene_id in (".", "..") or scene_id in scene_ids:
            raise ValueError("ID сцены должен быть уникальным и содержать только латинские буквы, цифры, точку, тире или подчёркивание")
        scene_ids.add(scene_id)
        if not scene.get("lines"):
            raise ValueError(f"В сцене «{scene.get('title', scene_id)}» нет реплик")
        image_mode = scene.get("image", {}).get("mode", "style")
        if image_mode not in ("style", "upload", "generated"):
            raise ValueError("Выбран неизвестный способ подготовки картинки")
        for line in scene.get("lines", []):
            if line["hero"] not in ids:
                raise ValueError(f"Для реплики {line.get('id')} не найден герой")
            if not str(line.get("text", "")).strip():
                raise ValueError("Текст реплики не может быть пустым")
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", str(line.get("id", ""))) or line["id"] in (".", ".."):
                raise ValueError("ID реплики содержит недопустимые символы")
            if line["id"] in line_ids:
                raise ValueError("ID реплик должны быть уникальными")
            line_ids.add(line["id"])


def legacy_who(hero_id: str, spec: dict) -> str:
    heroes = spec.get("heroes", [])
    idx = next((i for i, h in enumerate(heroes) if h["id"] == hero_id), 0)
    return "b" if idx == 0 else "m"


def renderer_timing(spec: dict) -> dict:
    data = timing_for(spec)
    for row in data["lines"]:
        row["who"] = legacy_who(row.pop("hero"), spec)
    return data


def artifact_state(project: dict) -> dict:
    spec = project["spec"]
    root = project_dir(project["id"])
    scenes = spec.get("script", {}).get("scenes", [])
    lines = [line for scene in scenes for line in scene.get("lines", [])]
    voice_hash = digest({"lines": lines, "heroes": spec.get("heroes"), "provider": "demo-silence-v1"})
    frame_hash = digest({"scenes": [{k: s.get(k) for k in ("id", "title", "visual_note", "image", "lines")} for s in scenes], "look": spec.get("look"), "renderer": RENDERER_VERSION})
    render_hash = digest({"voice": voice_hash, "frames": frame_hash, "timing": timing_for(spec), "format": spec.get("format"), "renderer": RENDERER_VERSION})
    voices_ready = (root / "audio" / "voice_track.mp3").exists() and (root / "voice.meta.json").exists()
    frames_ready = (root / "frames").exists() and all((root / "frames" / f"{s['id']}.jpg").exists() for s in scenes)
    render_ready = (root / "renders" / "draft.mp4").exists()
    vm = json.loads((root / "voice.meta.json").read_text(encoding="utf-8")) if (root / "voice.meta.json").exists() else {}
    fm = json.loads((root / "frames.meta.json").read_text(encoding="utf-8")) if (root / "frames.meta.json").exists() else {}
    rm = json.loads((root / "render.meta.json").read_text(encoding="utf-8")) if (root / "render.meta.json").exists() else {}
    def status(ready, old, hash_value):
        return "missing" if not ready else ("ready" if old == hash_value else "stale")
    return {
        "voice": status(voices_ready, vm.get("hash"), voice_hash),
        "frames": status(frames_ready, fm.get("hash"), frame_hash),
        "render": status(render_ready, rm.get("hash"), render_hash),
        "voice_units": len(lines), "scene_units": len(scenes),
        "timing": timing_for(spec), "voice_hash": voice_hash, "frame_hash": frame_hash, "render_hash": render_hash,
        "video_url": f"/media/{project['id']}/renders/draft.mp4" if render_ready else None,
        "duration_s": round(timing_for(spec)["total"], 1),
        "stale_reasons": ["Изменён сценарий, голос или оформление" ] if render_ready and rm.get("hash") != render_hash else [],
    }
