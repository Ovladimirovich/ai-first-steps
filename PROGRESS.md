# Прогресс производства

| Этап | Статус |
|---|---|
| Сценарий v1.1 оригинал | ✅ утверждён, 85 реплик (`script/lines.json`) |
| Сценарий Pixar «Зачем ИИ школьнику» | ✅ 246 строк, 57 реплик (`script/lines_pixar_why_ai.json`) |
| Голоса оригинал | ✅ Бит=voice-00, Маша=voice-01, 85/85 mp3 |
| Голоса Pixar | ✅ 57/57 mp3 `assets/audio/voice-pixar/` 1.4МБ, склейка `voice_track-pixar.mp3` 2.9МБ 379с |
| Тайминг оригинал | ✅ `timing.json` 695с + `ru.srt` |
| Тайминг Pixar | ✅ `timing-pixar.json` 379.0с 71 cue + `ru-pixar.srt` (реальный ffprobe) |
| Remotion оригинал | ✅ 30 сцен `S0_1…S8_2`, `Main` 11:45, титры, музыка с дакингом |
| Remotion Pixar | ✅ 25 сцен `PS0_1…PS8_2` + `PlaceholderPixar`, `PixarCard/Characters`, `PixarMain` 6:19 (11550 кадров) |
| FFmpeg-ветка | ✅ `tools/build_ffmpeg_video.py` Pillow+MoviePy 1920×1080 114 картинок 379с → 26МБ за 5:18 medium / 3 мин ultrafast |
| Превью | ✅ `preview/pixar-why-ai-preview.mp4` 7.8МБ 6:18 (FFmpeg цвет+voice+subs), `preview/pixar-why-ai-ffmpeg.mp4` 26МБ 6:19 |
| Финальный рендер оригинал | ✅ `release/final.mp4` 52МБ, `release/final_nosubs_720p.mp4` |
| Финальный рендер Pixar Remotion | ✅ чанки `tools/render_pixar_chunks.sh` (1500к) + cloud `render-pixar.yml` ~60 мин |
| Финальный рендер Pixar FFmpeg | ✅ cloud `render-ffmpeg.yml` ~4 мин, локально `python tools/build_ffmpeg_video.py` 3-5 мин |
| Раскадровка | ✅ `storyboard/storyboard.pdf` (оригинал), `storyboard_pixar.pdf` — next |
| Документация | ✅ `README.md` + `README_PIXAR.md` + `docs/00-08` подробно (Windows, Actions, архитектура, pipelines, troubleshooting) |
| CI | ✅ 2 workflow: `Render Pixar` + `Render FFmpeg` (free, artifacts 7д) |

## AI Video Factory

| Этап | Статус |
|---|---|
| Планирование | ✅ План согласован; контракт спеки и UX: `docs/factory/PLAN.md` |
| M0 — каркас | ✅ `python -m factory`, русскоязычные 5 шагов, локальное хранение в `.factory/` |
| M1 — сквозной прогон | ✅ демо-сценарий → немые аудиозаглушки → кадры → настоящий MP4 в плеере; перед каждым этапом смета и подтверждение |
| Кэш | ✅ повторно используются неизменённые MP3 реплик, кадры и MP4-сегменты сцен; смета показывает число изменившихся сцен |
| M2 — текст и голос | 🟡 llama.cpp с JSON-режимом и локальным repair, необязательный GigaChat и Piper CLI-адаптер подключены. Пользователь проверил реальные Piper-пробы на Windows: WAV генерируются и проигрываются, но речь неразборчива; Piper не принят, требуется сравнение/диагностика локальных TTS. Демо-тишина остаётся безопасным default |
| M3 — изображения и сцены | 🟡 загрузка фонов, промпты и история вариантов в фабрике готовы, ComfyUI пока не интегрирован. Пользователь вручную подтвердил медленную локальную генерацию на CPU и успешный Agnes workflow через API; Agnes — облачный путь с ключом в ComfyUI, тариф ещё не зафиксирован. Внешние вызовы из фабрики — только с явным согласием |
| M4 — доводка | 🟡 список проектов, SRT, Piper-настройки и проигрываемые WAV-пробы доступны; рабочий порядок команды и следующие этапы описаны в [дорожной карте](docs/factory/ROADMAP.md) |
| Studio F1 — схема/ревизии/миграция | ✅ v2 spec + production, v1 adapter, явный dry-run/apply, snapshots/restore, persisted drafts API; legacy migration remains explicit |
| Studio F2 — ассеты/fingerprints | ✅ content-addressed asset versions, append-only manifest, dependency fingerprints, separate Preview/Final; local Pillow/FFmpeg end-to-end MP4 smoke-test and unchanged-render cache reuse passed in a temporary project |
| Studio F3 — журнал/очередь | ✅ append-only hash-chain action journal, consent/cost/fingerprint gates, persistent sequential queue, cancellation/retry/recovery; generator inputs are deep-copied to preserve candidate base; apply uses story-hash guard, recovers safe legacy candidates, and ignores UI-only revision bumps; Windows job reads retry transient sharing locks; legacy job-state facade retained |
| Studio F4 — UI draft/review/apply | ✅ Browser flow wired to F3 APIs: proposal → explicit consent/cost ceiling → persistent job status → candidate diff → apply/reject; automated UI-state checks and manual click-through on a disposable project passed |
| Studio F5 — visual prompts/variant history | 🟡 Backend and UI implemented: versioned prompts/references, immutable image candidates, review/select/reject/deselect history and stale marking; no image provider is called; 6 backend tests plus UI-state coverage pass; manual browser click-through remains |
| Инструкции команды | ✅ Роли Arena/local engineer, безопасная передача задач и формат проверки описаны в `docs/factory/ARENA_ENGINEER_INSTRUCTIONS.md`, `LOCAL_ENGINEER_INSTRUCTIONS.md`, `DEVELOPMENT_WORKFLOW.md`; продуктовый статус остаётся в `ROADMAP.md` |
| M4 — расширенная доводка | ⏳ следующий этап |

Проверки фабрики на коммите `cb3dcb9`: `.venv/bin/python -m unittest discover -s tests -v` — **64/64**; UI-тесты, Python compilation и `git diff --check` проходят. Пользователь отдельно сообщил: Windows `pytest tests/test_voice.py -v` — 6/6, реальные Piper WAV созданы и проигрываются, но субъективно речь неразборчива; это не является подтверждением качества TTS. F1/F2/F3/F4/F5 тесты покрывают миграцию, revisions, fingerprints, immutable assets, очередь/отмену, visual variants и UI-state. End-to-end smoke-test MP4 на временном проекте с Pillow/FFmpeg и повторным использованием render cache пройден. Для дальнейшего плана и приемочных критериев см. [docs/factory/ROADMAP.md](docs/factory/ROADMAP.md).

## Сдано 27.10.2026 (оригинал)
- release/final.mp4, release/final_nosubs.mp4, ru.srt, script/scenario.md+.docx, factcheck.md, storyboard.pdf, credits.md, README

## Сдано 30.10.2026 (Pixar + FFmpeg)
- `arena/750486c0-ai-first-steps` @ `f0265df` — 25 Pixar-сцен, 57 озвучек, 2 тракта рендера, 2 cloud workflow, `docs/` 8 файлов
- `preview/pixar-why-ai-preview.mp4` 7.8МБ, `preview/pixar-why-ai-ffmpeg.mp4` 26МБ (локально), `pixar-style-preview.jpg`
- `remotion/public/timing-pixar.json` + `voice_track-pixar.mp3` + `ru-pixar.srt`
- `tools/build_ffmpeg_video.py` (3-5 мин) + `tools/render_pixar_chunks.sh` (чанк Remotion)
