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

## Сдано 27.10.2026 (оригинал)
- release/final.mp4, release/final_nosubs.mp4, ru.srt, script/scenario.md+.docx, factcheck.md, storyboard.pdf, credits.md, README

## Сдано 30.10.2026 (Pixar + FFmpeg)
- `arena/750486c0-ai-first-steps` @ `f0265df` — 25 Pixar-сцен, 57 озвучек, 2 тракта рендера, 2 cloud workflow, `docs/` 8 файлов
- `preview/pixar-why-ai-preview.mp4` 7.8МБ, `preview/pixar-why-ai-ffmpeg.mp4` 26МБ (локально), `pixar-style-preview.jpg`
- `remotion/public/timing-pixar.json` + `voice_track-pixar.mp3` + `ru-pixar.srt`
- `tools/build_ffmpeg_video.py` (3-5 мин) + `tools/render_pixar_chunks.sh` (чанк Remotion)
