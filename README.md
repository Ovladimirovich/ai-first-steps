# «Первые шаги в ИИ» — анимированная презентация для 5–8 классов

Видеообъяснение, где объясняются базовые понятия искусственного интеллекта с
помощью анимации из 30 сцен и озвучки. Создано на базе [Remotion](https://remotion.dev) (React + TypeScript).

![Размер репозитория: 12 MB](#)  
*В репозитории — только исходники и материалы. Сборка генерирует `release/` (около 80 МБ видео).*

---

## Содержание

- [Результаты](#результаты)
- [Как пересобрать](#как-пересобрать)
- [Структура репозитория](#структура-репозитория)
- [Как заменить реплику](#как-заменить-реплику)
- [Чек-лист перед показом](#чек-лист-перед-показом)
- [Лицензии](#лицензии)

---

## Результаты

| Файл | Что это |
|---|---|
| `release/final.mp4` | Готовое видео 1920×1080, 30 fps, H.264 (CRF 26, 52 МБ), с вшитыми субтитрами и озвучкой. Мастер-версия CRF 18 пересобирается `tools/render_chunks.sh final.mp4` |
| `release/final_nosubs_720p.mp4` | Версия без субтитров, 720p (для показа с отдельным SRT; 1080p пересобирается `tools/render_chunks.sh final_nosubs.mp4 --props='{"subs":false}'`) |
| `subtitles/ru.srt` | Субтитры (SRT) |
| `script/scenario.md` / `script/scenario.docx` | Сценарий v1.1 с таймкодами |
| `script/factcheck.md` | Проверка фактов блоков 4 и 7 с источниками |
| `storyboard/storyboard.pdf` | Раскадровка — ключевой кадр каждой из 30 сцен |
| `credits.md` | Инструменты, лицензии, товарные знаки |
| `plan_ai_presentation.md` | Исходный производственный план |

---

## Как пересобрать

### 1. Подготовка (Windows)

Установить [Python 3.11+](https://www.python.org/downloads/), добавить в PATH.
Установить зависимости генерации таймлайна:

```bash
pip install imageio-ffmpeg numpy
```

### 2. Сборка

```bash
# Генерирует timing.json, voice_track.mp3, music_ducked.mp3, subtitles/ru.srt
python tools/build_timeline.py

# Перейти в папку Remotion-проекта
cd remotion

# Установить зависимости
npm i

# Запустить Remotion Studio (http://localhost:3000)
npm run dev

# Собрать финальный MP4 (1920x1080, 30 fps, H.264)
npm run render
```

Параметры сборки:

```bash
# Без субтитров, 720p
npm run render:nosubs
```

Границы сцен вычисляются автоматически из таймкодов озвучки: после правки
реплики всё сместится самопроизвольно.

---

## Структура репозитория

```
ai-first-steps/
├── assets/
│   └── audio/
│       ├── voice/          # Реплики по сценам (s<сцена>_<b|m>_<номер>.mp3)
│       ├── backgrounds/    # Фоновые изображения
│       ├── characters/     # Герои
│       └── demo/           # Демо-аудио
├── remotion/               # Remotion-проект (описание анимации)
│   ├── src/
│   │   ├── scenes/         # Сцены по файлу (S0_1.tsx … S8_2.tsx)
│   │   ├── components/     # Компоненты (персонажи, карточки)
│   │   └── Main.tsx        # Точка входа
│   └── public/
│       ├── audio/          # Голосовая дорожка (генерируется build_timeline.py)
│       └── timing.json     # Таймкоды всех реплик (генерируется)
├── script/                 # Сценарий, реплики, фактчек
│   ├── scenario.md         # Текстовый сценарий
│   ├── scenario.docx       # Word-версия
│   ├── lines.json          # 85 реплик — единый источник для озвучки/субтитров
│   └── factcheck.md        # Проверка фактов блоков 4 и 7
├── tools/                  # Скрипты сборки
│   ├── build_timeline.py   # Генерация таймлайна/SRT/голосовой дорожки
│   └── render_chunks.sh    # Построчный рендер на низком объёме памяти
├── prototype/              # Ранний HTML-прототип (7 сцен)
├── storyboard/             # Раскадровка (PDF)
├── subtitles/              # ru.srt
├── release/                # Сгенерированные видео (игнорируются Git)
└── LICENSE / credits.md
```

---

## Как заменить реплику

1. Исправить текст в `script/scenario.md` и `script/lines.json`
   (или перегенерировать `lines.json` скриптом из истории проекта).
2. Записать новый `assets/audio/voice/<id>.mp3` (имя: `s<сцена>_<b|m>_<номер>.mp3`).
3. `python tools/build_timeline.py` → `npm run render`.

---

## Чек-лист перед показом

- [ ] Повторный фактчек блока 4 (сервисы обновляются раз в 1–3 месяца), обновить дату в `S8_2.tsx` и `credits.md`
- [ ] Прогон на фокус-группе 5–8 классов (4 главные мысли пересказывают без подсказки)
- [ ] Проверка громкости на школьной акустике

---

## Лицензии

Основной код (`remotion/`) licenced под **MIT** (см. `LICENSE`).

Полный разбор лицензий для каждого компонента:

| Компонент | Лицензия | Ссылки |
|---|---|---|
| `tools/build_timeline.py`, `remotion/` | MIT | — |
| `assets/audio/music_ducked.mp3`, `voice_track.mp3` (сгенерированные) | CC0 | — |
| `script/factcheck.md` (проверка фактов) | Собственная работа | — |
| `assets/audio/voice/*.mp3` (описанные реплики) | Собственная работа (TTS-API) | — |
| Шрифты (Montserrat/Inter/Noto Color Emoji) | OFL | — |
| SVG-иконки в `remotion/src/components` | CC BY-NC 4.0 | — |
| Эффекты мощности звука (loudnorm, sidechaincompress) | LGPL/GPL | — |
