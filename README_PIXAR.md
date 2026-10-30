# Pixar-версия: «Зачем ИИ школьнику» — 6:19 для 5–8 классов

**Тема:** 4 суперсилы ИИ для школьника · **Стиль:** Pixar 3D тёплый свет `#FFF6E0`, объём, тени, блики · **Хроно:** 379с 57 реплик · **Движок:** Remotion 4.0.300 + FFmpeg Pillow/MoviePy

Ветка `arena/750486c0-ai-first-steps` самодостаточна — клонируй её:
```bash
git clone --branch arena/750486c0-ai-first-steps https://github.com/Ovladimirovich/ai-first-steps.git
```

> Подробная документация — `docs/` (особенно [docs/02_QUICKSTART_WINDOWS.md](docs/02_QUICKSTART_WINDOWS.md) и [docs/05_PIPELINES.md](docs/05_PIPELINES.md))

---

## Что готово

| Файл | Что |
|---|---|
| `script/scenario_why_ai_pixar.md` 246 строк | Сценарий 8 блоков 11:00 → ужат до 6:19 |
| `script/lines_pixar_why_ai.json` 57 реплик | Бит/Маша `p0_1_m_01`…`p8_2_b_03` |
| `assets/audio/voice-pixar/` 57 mp3 1.4МБ | TTS voice-00/01 + склейка |
| `remotion/public/timing-pixar.json` 379.0с 71 cue → 57 lines | Реальный тайминг через `ffprobe` |
| `remotion/public/audio/voice_track-pixar.mp3` 2.9МБ | Склейка 57 mp3 |
| `subtitles/ru-pixar.srt` 8.5К | ≤42×2 строк |
| `remotion/src/pixarTheme.ts` | `P.bg #FFF6E0`, `teal #2EE6D6`, `yellow #FFD23F`, тень `0 20px 60px` |
| `remotion/src/components/PixarCard.tsx` | Карточка `w1400 r28` блик `linear-gradient(white.18, transparent)` + `spring 13/140` |
| `remotion/src/components/PixarCharacters.tsx` | Бит кубик-градиент/SSS, Маша худи |
| `remotion/src/pixarScenes/PS*.tsx` **25 сцен** | `PS0_1`…`PS8_2` + `PlaceholderPixar` |
| `remotion/src/PixarMain.tsx` + `Root.tsx` | Композиция `PixarWhyAI` 1920×1080 30fps `durationInFrames ceil((379+6)*30)=11550` |
| `assets/pixar/classroom_pixar.jpg` 274К, `clouds_pixar_bg.jpg` 86К | Фоны мастерской |
| `tools/build_pixar_timing.py` / `build_pixar_real_timeline.py` | Эмуляция по тексту vs реальный `ffprobe` |
| `tools/build_ffmpeg_video.py` ★ | **FFmpeg-ветка 3-5 мин** 1920×1080 114 картинок + MoviePy |
| `tools/render_pixar_chunks.sh` | Чанки по 1500 кадров для слабых ПК (`preview/chunks_pixar`) |
| `preview/pixar-why-ai-preview.mp4` 7.8МБ 6:18 | Превью FFmpeg цвет+voice+subs (уже готов) |
| `preview/pixar-why-ai-ffmpeg.mp4` 26МБ 6:19 | **Финал FFmpeg 5:18 medium** |
| `.github/workflows/render-pixar.yml` | Cloud Remotion ~60 мин |
| `.github/workflows/render-ffmpeg.yml` | **Cloud FFmpeg ~4 мин ultrafast** |

---

## Как посмотреть

```bash
cd remotion && npm i && npx remotion browser ensure
npm run dev   # http://localhost:3000 → выбери PixarWhyAI → Play
```

Превью уже готов без рендера: `preview/pixar-why-ai-preview.mp4` / `preview/pixar-why-ai-ffmpeg.mp4` — открывай в VLC.

---

## Как собрать (2 тракта, один тайминг)

**Озвучка (уже есть):** 57 mp3 в `assets/audio/voice-pixar/` → `python tools/build_pixar_real_timeline.py` → `timing-pixar.json` + `voice_track-pixar.mp3`

**Тракт A — Remotion (красиво, 50 мин):**
```bash
cd remotion
npx remotion render src/index.ts PixarWhyAI ../release/pixar-why-ai-full.mp4 --codec h264 --crf 18 --concurrency 4
# чанками: bash ../tools/render_pixar_chunks.sh pixar-why-ai-full.mp4
```

**Тракт B — FFmpeg (быстро, 3-5 мин, рекомендуется):**
```bash
pip install Pillow moviepy==1.0.3 imageio-ffmpeg
python tools/build_ffmpeg_video.py --output release/pixar-why-ai-ffmpeg.mp4 --crf 18 --preset medium
python tools/build_ffmpeg_video.py --preview --output preview/pixar-why-ai-ffmpeg-preview.mp4  # 720p 1 мин
python tools/build_ffmpeg_video.py --only 10 --output /tmp/test.mp4 --no-audio --preset ultrafast  # тест
```

Оба берут `timing-pixar.json` + `voice_track-pixar.mp3`. Подробное сравнение — [docs/05_PIPELINES.md](docs/05_PIPELINES.md).

**Облако бесплатно:** `https://github.com/Ovladimirovich/ai-first-steps/actions` → `Render Pixar WHY AI` (60 мин) или `Render FFmpeg WHY AI` (4 мин) → `Run workflow` → качай artifact 7 дней.

---

## 8 блоков — 4 суперсилы

| Блок | Время | Суперсила |
|---|---|---|
| 0 | 0:00–0:28 | Хук: 2 часа vs 10 мин |
| 1 | 0:29–1:33 | Репетитор 24/7 (пиццерия, Майнкрафт) |
| 2 | 1:35–2:31 | Творец: промпт → шум 50 шагов → постер |
| 3 | 2:33–2:51 | Чек: честно ли сдать чужое? |
| 4 | 2:52–3:50 | Исследователь: идеи → план → код |
| 5 | 3:51–4:41 | Профессия будущего |
| 6 | 4:43–5:27 | 3 щита: Проверяй / Указывай / Береги |
| 7 | 5:28–5:43 | Чек: сделает умнее сам? |
| 8 | 5:45–6:19 | 4 карточки + челлендж на неделю |

Подробно — `script/scenario_why_ai_pixar.md`, по сценам — [docs/06_PIXAR_SCENES.md](docs/06_PIXAR_SCENES.md).

---

## Чем отличается от оригинала

| Оригинал `Main` 11:45 | Pixar `PixarWhyAI` 6:19 |
|---|---|
| `#1B2A4A` холодный, flat SVG | `#FFF6E0` тёплый, градиенты, облака 0.18 |
| `Card.tsx` плоские | `PixarCard.tsx` объём: `shadow 0 20px 60px + inset блик + inset тень`, `spring` |
| `S0_1…S8_2` инфографика 30 сцен | `PS0_1…PS8_2` мастерская/пиццерия/прогрессбар 25 сцен |
| «что такое ИИ» теория | «зачем ИИ тебе» мотивация + портфолио + челлендж |

Конвейер `sceneRanges()` + субтитры + музыка — тот же.

---

## Что дальше

* Дорисовать фоны для каждой сцены (Blender/AI) → `remotion/public/pixar/`
* `npx remotion still` → `storyboard/storyboard_pixar.pdf`
* Добавить `spring` в FFmpeg-ветку (сейчас статичные карточки) — будет 7 мин но с анимацией

Полный чек-лист — [docs/01_OVERVIEW.md](docs/01_OVERVIEW.md), правка реплик — [docs/07_TIMELINE_VOICE.md](docs/07_TIMELINE_VOICE.md), проблемы — [docs/08_TROUBLESHOOTING.md](docs/08_TROUBLESHOOTING.md).
