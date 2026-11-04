from __future__ import annotations

import copy
import hashlib
import json
import mimetypes
import re
import time
import uuid
from pathlib import Path
from typing import Any

from .revisions import create_revision, list_revisions as _list_revisions, read_revision as _read_revision
from .schema_v2 import empty_asset_manifest, merge_v1_view, validate_production, validate_story_v2, v1_to_v2, v2_to_v1
from .storage import atomic_write_json, project_lock
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


def _read_asset_manifest(directory: Path) -> dict:
    path = directory / "studio" / "assets.json"
    if not path.exists():
        return empty_asset_manifest()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Реестр ассетов повреждён: {path}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("assets"), list):
        raise ValueError(f"Некорректная структура реестра ассетов: {path}")
    return value


def _read_v2_state(directory: Path, metadata: dict) -> tuple[dict, dict]:
    revision_id = metadata.get("current_revision_id")
    if revision_id:
        try:
            revision = _read_revision(directory, str(revision_id))
            return revision["spec"], revision["production"]
        except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Текущий снимок ревизии {revision_id} повреждён или отсутствует; автоматический откат не выполнен") from exc
    spec_path, production_path = directory / "spec.json", directory / "production.json"
    if spec_path.is_file() and production_path.is_file():
        return json.loads(spec_path.read_text(encoding="utf-8")), json.loads(production_path.read_text(encoding="utf-8"))
    raise ValueError(f"Не найдены данные текущей ревизии проекта {metadata.get('id', '')}")


def load_project(project_id: str) -> dict:
    directory = project_dir(project_id)
    path = directory / "project.json"
    if not path.exists():
        raise FileNotFoundError(project_id)
    project = json.loads(path.read_text(encoding="utf-8"))
    if int(project.get("schema_version", 1)) >= 2:
        story, production = _read_v2_state(directory, project)
        validate_story_v2(story)
        validate_production(production)
        manifest = _read_asset_manifest(directory)
        project["spec"] = v2_to_v1(story, production, manifest)
        if project["spec"].get("script", {}).get("scenes"):
            validate_spec(project["spec"])
    else:
        project["spec"] = json.loads((directory / "spec.json").read_text(encoding="utf-8"))
    return project


def _asset_record_for_legacy_path(directory: Path, scene_id: str, relative: str) -> dict | None:
    candidate = (directory / relative).resolve()
    if directory.resolve() not in candidate.parents or not candidate.is_file():
        return None
    digest_value = hashlib.sha256(candidate.read_bytes()).hexdigest()
    asset_id = "upload-" + hashlib.sha256(f"{Path(relative).as_posix()}|{digest_value}".encode("utf-8")).hexdigest()[:20]
    return {"asset_id": asset_id, "type": "scene_image", "target": {"scene_id": scene_id},
            "sequence": 1, "asset_version": 1, "path": Path(relative).as_posix(), "sha256": digest_value,
            "mime": mimetypes.guess_type(candidate.name)[0] or "application/octet-stream",
            "size_bytes": candidate.stat().st_size, "source": "uploaded", "provenance": "legacy_upload",
            "input_fingerprint": None, "created_at": candidate.stat().st_mtime}


def _sync_legacy_assets(directory: Path, story: dict, production: dict, manifest: dict) -> dict:
    assets = manifest.setdefault("assets", [])
    by_path = {str(item.get("path")): item for item in assets if item.get("path")}
    by_id = {str(item.get("asset_id")): item for item in assets if item.get("asset_id")}
    for scene_id, visual in production.get("visuals", {}).items():
        if visual.get("image_mode") != "upload":
            visual["selected_asset_id"] = None
            continue
        relative = visual.get("legacy_path")
        if not relative:
            continue
        normalized = Path(str(relative)).as_posix()
        record = by_path.get(normalized)
        candidate = (directory / normalized).resolve()
        if directory.resolve() not in candidate.parents or not candidate.is_file():
            # Keep the legacy reference visible; the migration planner will report missing files.
            continue
        current_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if record and record.get("sha256") == current_hash:
            visual["selected_asset_id"] = record["asset_id"]
            continue
        record = _asset_record_for_legacy_path(directory, str(scene_id), normalized)
        if record:
            next_asset_version = 1 + max((int(item.get("asset_version", 0)) for item in assets
                                          if item.get("type") == "scene_image" and
                                          item.get("target", {}).get("scene_id") == str(scene_id)), default=0)
            record["asset_version"] = next_asset_version
            record["sequence"] = next_asset_version
            existing = by_id.get(record["asset_id"])
            if existing is None:
                assets.append(record)
                by_id[record["asset_id"]] = record
            visual["selected_asset_id"] = record["asset_id"]
            by_path[normalized] = record
    return manifest


def _metadata_only(project: dict) -> dict:
    return {key: value for key, value in project.items() if key not in ("spec", "production", "_storage", "_native_update")}


def _mirror_v2(directory: Path, story: dict, production: dict) -> None:
    atomic_write_json(directory / "spec.json", story)
    atomic_write_json(directory / "production.json", production)


def _create_v2_project(project: dict, story: dict, production: dict) -> None:
    directory = project_dir(project["id"])
    directory.mkdir(parents=True, exist_ok=True)
    manifest = empty_asset_manifest()
    project.update({"schema_version": 2, "project_revision": int(project.get("revision", 1)),
                    "spec_revision": 1, "production_revision": 1, "revision_sequence": 1})
    revision = create_revision(directory, story, production, sequence=1,
                               project_revision=int(project.get("revision", 1)), spec_revision=1,
                               production_revision=1, parent_revision_id=None,
                               changed_domains=["baseline"], actor="system", reason="project_created")
    project["current_revision_id"] = revision["revision_id"]
    atomic_write_json(directory / "studio" / "assets.json", manifest)
    _mirror_v2(directory, story, production)
    atomic_write_json(directory / "project.json", _metadata_only(project))


def save_project(project: dict) -> None:
    directory = project_dir(project["id"])
    directory.mkdir(parents=True, exist_ok=True)
    with project_lock(project["id"]):
        metadata_path = directory / "project.json"
        try:
            stored_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stored_metadata = {}
        if stored_metadata:
            current_revision = int(stored_metadata.get("revision", 1))
            if int(project.get("revision", -1)) != current_revision + 1:
                raise ValueError("Проект изменился в другой вкладке. Обновите страницу перед сохранением.")
        if int(stored_metadata.get("schema_version", 1)) < 2:
            # Existing v1 projects stay v1 until the user explicitly migrates them.
            atomic_write_json(directory / "spec.json", project["spec"])
            atomic_write_json(metadata_path, _metadata_only(project))
            return

        current_story, current_production = _read_v2_state(directory, stored_metadata)
        manifest = _read_asset_manifest(directory)
        native_update = project.get("_native_update")
        if native_update:
            story = copy.deepcopy(native_update["spec"])
            production = copy.deepcopy(native_update["production"])
        else:
            story, production = merge_v1_view(project["spec"], current_story, current_production)
        manifest = _sync_legacy_assets(directory, story, production, manifest)
        validate_story_v2(story)
        validate_production(production)
        story_changed = digest(story) != digest(current_story)
        production_changed = digest(production) != digest(current_production)
        current_revision = int(stored_metadata.get("revision", 1))
        next_project_revision = max(int(project.get("revision", current_revision)), current_revision)
        if (story_changed or production_changed) and next_project_revision <= current_revision:
            next_project_revision = current_revision + 1
        spec_revision = int(stored_metadata.get("spec_revision", 1)) + int(story_changed)
        production_revision = int(stored_metadata.get("production_revision", 1)) + int(production_changed)
        revision_id = stored_metadata.get("current_revision_id")
        sequence = int(stored_metadata.get("revision_sequence", 1))
        if story_changed or production_changed:
            sequence += 1
            created = create_revision(directory, story, production, sequence=sequence,
                                      project_revision=next_project_revision,
                                      spec_revision=spec_revision,
                                      production_revision=production_revision,
                                      parent_revision_id=revision_id,
                                      changed_domains=[name for name, changed in (("spec", story_changed), ("production", production_changed)) if changed],
                                      actor="user", reason="accepted_legacy_patch")
            revision_id = created["revision_id"]
        atomic_write_json(directory / "studio" / "assets.json", manifest)
        updated = _metadata_only(project)
        updated.update({"schema_version": 2, "revision": next_project_revision,
                        "project_revision": next_project_revision,
                        "spec_revision": spec_revision, "production_revision": production_revision,
                        "revision_sequence": sequence, "current_revision_id": revision_id})
        # The metadata pointer is the commit point; readers use its immutable revision snapshot.
        atomic_write_json(metadata_path, updated)
        _mirror_v2(directory, story, production)
        project.update({"schema_version": 2, "revision": next_project_revision,
                        "project_revision": next_project_revision,
                        "spec_revision": spec_revision, "production_revision": production_revision,
                        "revision_sequence": sequence, "current_revision_id": revision_id})


def get_studio_document(project_id: str) -> dict:
    project = load_project(project_id)
    directory = project_dir(project_id)
    if int(project.get("schema_version", 1)) >= 2:
        story, production = _read_v2_state(directory, project)
        manifest = _read_asset_manifest(directory)
        schema_version = 2
    else:
        story, production = v1_to_v2(project["spec"])
        manifest = empty_asset_manifest()
        schema_version = 1
    return {"project_id": project_id, "schema_version": schema_version,
            "project_revision": int(project.get("revision", 1)),
            "spec_revision": int(project.get("spec_revision", 0)),
            "production_revision": int(project.get("production_revision", 0)),
            "current_revision_id": project.get("current_revision_id"),
            "spec": story, "production": production, "assets": manifest,
            "migration_required": schema_version == 1}


def project_revisions(project_id: str) -> list[dict]:
    if int(json.loads((project_dir(project_id) / "project.json").read_text(encoding="utf-8")).get("schema_version", 1)) < 2:
        return []
    metadata = json.loads((project_dir(project_id) / "project.json").read_text(encoding="utf-8"))
    return [dict(item, is_current=item.get("revision_id") == metadata.get("current_revision_id"))
            for item in _list_revisions(project_dir(project_id))]


def get_project_revision(project_id: str, revision_id: str) -> dict:
    directory = project_dir(project_id)
    metadata = json.loads((directory / "project.json").read_text(encoding="utf-8"))
    if int(metadata.get("schema_version", 1)) < 2:
        raise ValueError("Сначала выполните явную миграцию проекта на v2")
    revision = _read_revision(directory, revision_id)
    return {key: value for key, value in revision.items() if key != "production"} | {
        "spec": revision["spec"], "production": revision["production"]}


def restore_project_revision(project_id: str, revision_id: str, expected_revision: int) -> dict:
    directory = project_dir(project_id)
    with project_lock(project_id):
        metadata_path = directory / "project.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if int(metadata.get("schema_version", 1)) < 2:
            raise ValueError("Сначала выполните явную миграцию проекта на v2")
        if int(metadata.get("revision", 1)) != int(expected_revision):
            raise ValueError("Проект изменился после просмотра истории. Обновите список ревизий.")
        target = _read_revision(directory, revision_id)
        current_story, current_production = _read_v2_state(directory, metadata)
        story_changed = digest(current_story) != digest(target["spec"])
        production_changed = digest(current_production) != digest(target["production"])
        if not story_changed and not production_changed:
            return load_project(project_id)
        project_revision = int(metadata.get("revision", 1)) + 1
        spec_revision = int(metadata.get("spec_revision", 1)) + int(story_changed)
        production_revision = int(metadata.get("production_revision", 1)) + int(production_changed)
        sequence = int(metadata.get("revision_sequence", 1)) + 1
        created = create_revision(directory, target["spec"], target["production"], sequence=sequence,
                                  project_revision=project_revision, spec_revision=spec_revision,
                                  production_revision=production_revision,
                                  parent_revision_id=metadata.get("current_revision_id"),
                                  changed_domains=[name for name, changed in (("spec", story_changed), ("production", production_changed)) if changed],
                                  actor="user", restored_from=revision_id, reason="restore_snapshot")
        restored_title = str(target["spec"].get("intent", {}).get("theme") or "Новый ролик")[:80]
        updated = {**metadata, "revision": project_revision, "project_revision": project_revision,
                   "spec_revision": spec_revision, "production_revision": production_revision, "revision_sequence": sequence,
                   "current_revision_id": created["revision_id"], "title": restored_title,
                   "updated_at": time.time()}
        atomic_write_json(metadata_path, updated)
        _mirror_v2(directory, target["spec"], target["production"])
        return load_project(project_id)


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
    legacy_spec = new_spec(theme, payload.get("audience", "Дети 11–14 лет"), duration, style)
    story, production = v1_to_v2(legacy_spec)
    project = {"id": project_id, "title": theme[:80] or "Новый ролик", "revision": 1,
               "current_step": 0, "created_at": time.time(), "updated_at": time.time()}
    _create_v2_project(project, story, production)
    return load_project(project_id)


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
