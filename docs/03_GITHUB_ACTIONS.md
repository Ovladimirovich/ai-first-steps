# 03 — Облачный рендер GitHub Actions (бесплатно, без твоего ПК)

Бесплатный рендер на `ubuntu-latest` — твой Xeon отдыхает. Работает даже если у тебя `Node 24` или нет Python.

## Что есть

| Workflow | Что делает | Время | Триггер |
|---|---|---|---|
| `Render Pixar WHY AI` | Remotion `PixarWhyAI` 11550 кадров, Node 20, `npm ci` + `browser ensure` + `remotion render --crf 18 --concurrency 2` | ~60-80 мин | `workflow_dispatch` |
| `Render FFmpeg WHY AI (fast)` | FFmpeg `build_ffmpeg_video.py` 114 картинок 1920×1080 + `mux voice`, Python 3.11 + `Pillow+moviepy` | **~4 мин ultrafast / ~6 мин medium** | `workflow_dispatch` |
| `Render` (если есть) | Оригинал `Main` | ~60 мин | — |

Файлы лежат `.github/workflows/render-pixar.yml` и `render-ffmpeg.yml` (в ветке `arena`).

## Как запустить (2 клика) — ВАЖНО про ветку

> **Почему у тебя пусто в Actions:** GitHub показывает в левом списке только workflow, которые есть в ветке `main` (default). Наши 2 файла пока только в `arena/750486c0-ai-first-steps`, поэтому список пуст. Это нормально.

**Решение на 1 клик — смерджи PR:**
1. Открой https://github.com/Ovladimirovich/ai-first-steps/pull/1 → `Merge pull request` → `Confirm merge`
2. Подожди 10с, обнови https://github.com/Ovladimirovich/ai-first-steps/actions — слева появятся `Render Pixar WHY AI` и `Render FFmpeg WHY AI`
3. Выбери нужный → `Run workflow` → ветка `arena/750486c0-ai-first-steps` → можно поменять `crf`/`preset`/`width` → `Run workflow`

**Если не хочешь мерджить сейчас — запусти без UI (работает и до мержа):**
```powershell
# из C:\Projects_arena (нужен gh: winget install GitHub.cli)
gh workflow run "Render Pixar WHY AI" --ref arena/750486c0-ai-first-steps
gh workflow run "Render FFmpeg WHY AI (fast 3-5 min)" --ref arena/750486c0-ai-first-steps
# или прямой API:
# gh api repos/Ovladimirovich/ai-first-steps/actions/workflows/render-ffmpeg.yml/dispatches -f ref=arena/750486c0-ai-first-steps -f inputs[preset]=ultrafast
```
Прямые ссылки на файлы (видны и до мержа): [render-pixar.yml](https://github.com/Ovladimirovich/ai-first-steps/blob/arena/750486c0-ai-first-steps/.github/workflows/render-pixar.yml) / [render-ffmpeg.yml](https://github.com/Ovladimirovich/ai-first-steps/blob/arena/750486c0-ai-first-steps/.github/workflows/render-ffmpeg.yml)

## Параметры (по клику Run)

* **Pixar Remotion:** `composition` (PixarWhyAI), `crf` (18), `concurrency` (2) — для 2 ядер раннера 2 оптимально, 4 не быстрее.
* **FFmpeg:** `crf` (18 high / 23 smaller), `preset` (ultrafast fastest / medium balanced / slow max quality), `width` (1920 full / 1280 preview)

## Где забрать видео

`Actions → твой запуск → внизу Artifacts`:
* `pixar-why-ai-full` (Remotion) или `pixar-ffmpeg-1920p` (FFmpeg) — внутри `release/pixar-*.mp4` + `preview/*.mp4`
* Хранится 7 дней, `compression-level: 0` (без сжатия), ~25-400МБ
* Если упал — качай `debug-preview` с `still-test.png`

Логи — прямо в браузере, вкладка `Run Render …` → `Render …` → live.

## Запуск из терминала (твоего `C:\Projects_arena\`)

Если поставил `gh` (GitHub CLI):
```powershell
gh workflow run "Render Pixar WHY AI" --ref arena/750486c0-ai-first-steps
gh workflow run "Render FFmpeg WHY AI (fast 3-5 min)" --ref arena/750486c0-ai-first-steps --field crf=18 --field preset=ultrafast --field width=1920
gh run list --limit 3
gh run watch
```

## Лимиты бесплатно

* Публичный репозиторий — **2000 мин/мес** бесплатно, 1 раннер, 6ч на джоб. Наш Remotion 60 мин × 20 запусков = 1200 мин → влезает. FFmpeg 4 мин × 100 запусков = 400 мин.
* Приватный — 500 мин/мес, тоже хватает на FFmpeg.
* Если апдейтишь ветку во время рендера — старый ран перезапустится, дождитесь.

## Когда что выбирать

* **Надо быстро показать заказчику/учителю** → FFmpeg workflow (4 мин) + скачай artifact, покажи `preview/pixar-why-ai-ffmpeg.mp4`.
* **Надо максимум красоты с веб-анимацией/пружинками** → Remotion workflow (60 мин) — `PixarCard` с бликами, `spring` анимация.
* **Нет интернета / outage GitHub** → рендерь локально по `02_QUICKSTART_WINDOWS.md` — не зависит от облака.
