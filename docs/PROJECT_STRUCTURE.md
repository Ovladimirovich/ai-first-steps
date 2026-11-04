# Структура проекта ai-first-steps

**Корень:** `C:\Projects_arena\ai-first-steps`
**Ветка:** `arena/9d50668a-ai-first-steps` (HEAD: `0dd6430` — PR #3 «FFmpeg motion3 spring+workshop+karaoke+SFX + new_topic конструктор»)
**Дата:** 30.10.2026

---

## Дерево папок (без node_modules)

```
ai-first-steps/
├── .github/
│   └── workflows/
│       ├── render-ffmpeg.yml      # CI: рендер через FFmpeg/MoviePy
│       └── render-pixar.yml       # CI: рендер через Remotion
├── assets/                        # ИСТОЧНИКИ ассетов (не копировать в public/)
│   ├── audio/
│   │   ├── voice/                 # 85 оригинальных голосовых файлов (s*.mp3)
│   │   └── voice-pixar/           # 57 голосовых файлов Pixar (p*.mp3)
│   └── pixar/                     # Изображения Pixar
│       ├── classroom_pixar.jpg
│       └── clouds_pixar_bg.jpg
├── docs/                          # Документация
│   ├── 00_INDEX.md
│   ├── 01_OVERVIEW.md
│   ├── 02_QUICKSTART_WINDOWS.md
│   ├── 03_GITHUB_ACTIONS.md
│   ├── 04_ARCHITECTURE.md
│   ├── 05_PIPELINES.md
│   ├── 06_PIXAR_SCENES.md
│   ├── 07_TIMELINE_VOICE.md
│   ├── 08_TROUBLESHOOTING.md
│   ├── INSTRUCTIONS_FOR_AI_ENGINEERS.md
│   └── PROJECT_STRUCTURE.md       # этот файл
├── preview/                       # Превью-ролики
│   ├── pixar-why-ai-full.mp4      # копия полного релиза
│   ├── pixar-why-ai-preview.mp4   # короткий превью (8 МБ)
│   └── voice_track-pixar.mp3      # звуковая дорожка для превью
├── prototype/                     # HTML-прототип
│   └── index.html                 # standalone демо (960×540)
├── release/                       # Финальные рендеры
│   ├── pixar-why-ai-full.mp4      # 75.7 МБ, Remotion, 6:19
│   └── pixar-why-ai-ffmpeg.mp4    # 25.4 МБ, MoviePy fallback
├── remotion/                      # Remotion Node.js проект (анимация)
│   ├── public/                    # Статические файлы (доступны в браузере при рендере)
│   │   ├── audio/
│   │   │   └── voice_track-pixar.mp3   (ссылка на assets/audio/voice-pixar/)
│   │   ├── pixar/                 # КОПИИ из assets/pixar/ (для ссылок в сценах)
│   │   │   ├── classroom_pixar.jpg
│   │   │   └── clouds_pixar_bg.jpg
│   │   ├── timing-pixar.json      # Таймкоды Pixar-ролика
│   │   └── timing.json            # Копия timing-pixar.json (для совместимости)
│   ├── src/
│   │   ├── scenes/                # Новые сцены S0_1 … S8_2 (+ Placeholder)
│   │   ├── pixarScenes/           # Оригинальные Pixar-сцены PS0_1 … PS8_2
│   │   ├── components/            # React-компоненты (BotCard, Card, Cat, …)
│   │   ├── index.ts               # Экспорт всех composições
│   │   ├── Main.tsx               # Оригинальная композиция Main
│   │   ├── PixarMain.tsx          # Композиция PixarWhyAI
│   │   ├── Root.tsx               # Точка входа Remotion
│   │   ├── pixarTheme.ts          # Цветовая палитра Pixar
│   │   └── theme.ts               # Общая тема
│   ├── package.json
│   ├── package-lock.json
│   └── tsconfig.json
├── script/                        # Сценарии и таймкоды
│   ├── factcheck.md
│   ├── lines.json
│   ├── lines_pixar_why_ai.json
│   ├── scenario.docx
│   ├── scenario.md
│   └── scenario_why_ai_pixar.md
├── storyboard/                    # Створіборд
│   └── storyboard.pdf
├── subtitles/                     # Субтитры
│   ├── ru-pixar.srt
│   └── ru.srt
├── tools/                         # Инструменты сборки (Python)
│   ├── build_ffmpeg_video.py      # Быстрый рендер через MoviePy + Pillow
│   ├── build_pixar_real_timeline.py
│   ├── build_pixar_timing.py      # Генерация timing-pixar.json
│   ├── build_timeline.py
│   ├── render_chunks.sh
│   └── render_pixar_chunks.sh
├── pixar-style-preview.jpg        # Фон мастерской (588 КБ)
├── plan_ai_presentation.md        # План презентации
├── PROGRESS.md                    # Прогресс разработки
├── README.md                      # Описание проекта
├── README_PIXAR.md                # Описание Pixar-ветки
├── credits.md                     # Авторы и ресурсы
├── LICENSE
├── run.bat                        # Скрипт запуска
└── stop.bat                       # Скрипт остановки
```

---

## Правила организации

### 1. `assets/` — только исходники
Все исходные ассеты (картинки, аудио) хранятся в `assets/`.  
В `remotion/public/` кладутся **копии** только тех файлов, которые нужны Remotion во время рендера (через `staticFile()` или CSS `url()`).

### 2. `remotion/public/` — для сборки
Файлы здесь доступны браузеру при рендере Remotion. Не редактировать вручную — копировать из `assets/`.

### 3. `remotion/src/scenes/` vs `remotion/src/pixarScenes/`
- `scenes/` — новые универсальные сцены (S0_1 … S8_2)
- `pixarScenes/` — оригинальные Pixar-сцены (PS0_1 … PS8_2)  
Обе папки имеют `index.tsx` и `Placeholder.tsx`. Не сливать без согласования.

### 4. `release/` и `preview/` — выходные данные
- `release/` — финальные MP4 (продукция)
- `preview/` — превью для быстрого просмотра + копия последнего релиза

### 5. `tools/` — скрипты сборки
Все Python-скрипты для генерации таймингов и рендеринга.

---

## Что НЕ делать

| Действие | Почему |
|----------|--------|
| Удалять `remotion/public/pixar/` | Сцены ссылаются на `pixar/clouds_pixar_bg.jpg` через CSS `url()` |
| Путать `scenes/` и `pixarScenes/` | Разные наборы сцен, разные composições |
| Редактировать файлы в `release/` | Это выходные данные, перезаписываются при рендере |
| Удалять `timing.json` из `remotion/public/` | `Main.tsx` и `Root.tsx` импортируют его |

