# 04 — Архитектура репозитория

```
ai-first-steps/   # репозиторий, ветка arena/750486c0-ai-first-steps самодостаточна (main не нужен)
├── .github/workflows/
│   ├── render-pixar.yml   # Remotion cloud 60 мин
│   └── render-ffmpeg.yml  # FFmpeg cloud 4 мин
├── assets/
│   ├── audio/voice/            # 85 wav оригинала s<сц>_<b|m>_<n>.mp3
│   ├── audio/voice-pixar/      # 57 mp3 Pixar p0_1_m_01.mp3 … p8_2_b_03.mp3 (1.4МБ)
│   └── pixar/                  # classroom_pixar.jpg, clouds_pixar_bg.jpg (AI-концепт)
├── remotion/                   # Remotion-проект (React+TS)
│   ├── src/
│   │   ├── scenes/             # 30 сцен оригинала S0_1.tsx … S8_2.tsx
│   │   ├── pixarScenes/        # 25 сцен Pixar PS0_1…PS8_2 + PlaceholderPixar
│   │   ├── components/         # Card.tsx, Characters.tsx, PixarCard.tsx, PixarCharacters.tsx
│   │   ├── pixarTheme.ts       # P.bg #FFF6E0, teal, yellow, coral
│   │   ├── Main.tsx            # Оригинал 11:45
│   │   ├── PixarMain.tsx       # Pixar 6:19 — читает timing-pixar.json + Audio voice_track-pixar
│   │   ├── Root.tsx            # регистрирует 2 композиции Main + PixarWhyAI
│   │   └── index.ts
│   ├── public/
│   │   ├── timing.json         # 85 cue оригинала (695с)
│   │   ├── timing-pixar.json   # 57 cue Pixar 379.0с 71 cue → реально 57 lines (генерит build_pixar_*)
│   │   ├── audio/voice_track.mp3 + voice_track-pixar.mp3  # склейки (5.4М + 2.9М)
│   │   └── pixar/              # копии фонов для staticFile()
│   ├── package.json            # remotion 4.0.300, @sparticuz/chromium для песочницы
│   └── …
├── script/
│   ├── lines.json              # 85 реплик оригинала — единый источник
│   ├── lines_pixar_why_ai.json # 57 реплик Pixar
│   ├── scenario.md / .docx     # сценарий оригинала v1.1
│   ├── scenario_why_ai_pixar.md# сценарий Pixar 11:00 8 блоков 57 реплик
│   └── factcheck.md
├── tools/
│   ├── build_timeline.py       # оригинал: voice/*.mp3 + lines.json → timing.json + voice_track + music_ducked + srt
│   ├── build_pixar_timing.py   # эмуляция по длине текста (до реальных mp3)
│   ├── build_pixar_real_timeline.py # реальный: voice-pixar/*.mp3 → timing-pixar.json 379с + srt + voice_track-pixar
│   ├── build_ffmpeg_video.py   # ★ FFmpeg-ветка: timing-pixar + voice → Pillow 114 картинок 1920x1080 → MoviePy → mp4 3-5 мин
│   └── render_chunks.sh / render_pixar_chunks.sh # чанки по 1500 кадров для слабых ПК/песочницы
├── subtitles/
│   ├── ru.srt, ru-pixar.srt
│   └── …
├── preview/                    # готовые превью (коммитятся): pixar-why-ai-preview.mp4 7.8МБ 6:18, pixar-why-ai-ffmpeg.mp4 26МБ
├── release/                    # финалы (игнор в .gitignore): final.mp4, pixar-why-ai-full.mp4, pixar-why-ai-ffmpeg.mp4
├── storyboard/                 # storyboard.pdf
├── plan_ai_presentation.md     # производственный план 12 этапов
├── credits.md, LICENSE, PROGRESS.md
├── README.md                   # оригинал
├── README_PIXAR.md             # Pixar
└── docs/                       # эта документация
```

## Поток данных

```
lines*.json (текст) 
  → assets/audio/voice*.mp3 (TTS или живые)
    → tools/build_*_timeline.py (ffprobe длительности)
      → remotion/public/timing*.json (start/end/dur per line) + voice_track*.mp3 (concat) + subtitles/ru*.srt
        → remotion/src/Main.tsx / PixarMain.tsx (читают timing, рисуют сцены, <Audio src=voice_track> + <Subtitle>)
          → Remotion Studio (превью) — или —
            → npx remotion render (Chrome → 11550 png → ffmpeg → mp4 50 мин) — или —
            → python tools/build_ffmpeg_video.py (Pillow 114 png → MoviePy → mp4 3-5 мин)
```

Границы сцен вычисляются автоматически из таймкодов — поправил реплику → всё сместится.

## Две композиции

`remotion/src/Root.tsx` регистрирует:
```tsx
<Composition id="Main" component={Main} durationInFrames={Math.ceil((timing.total+6)*30)} ... />
<Composition id="PixarWhyAI" component={PixarMain} durationInFrames={Math.ceil((timingPixar.total+6)*30)} ... />
```

Переключение в Studio — выпадающий список вверху. `pixarTheme.ts` — тёплая палитра вместо холодной, `PixarCard` — объём (тень 0 20px 60px, блик `linear-gradient(white.18, transparent)`, `spring` с `damping 13`).

## Где что править

* Текст реплики → `script/lines*.json` + `scenario*.md` → перезапись mp3 → `build_*_timeline.py`
* Визуал сцены → `remotion/src/scenes/*.tsx` или `pixarScenes/PS*.tsx` (копируй `PS1_2` как шаблон)
* Карточка/персонаж → `components/PixarCard.tsx` / `PixarCharacters.tsx`
* Тайминг → не править руками, генерить скриптом
* Субтитры → генерит скрипт (≤42 символа ×2 строки), правишь `subtitles/*.srt` если надо
