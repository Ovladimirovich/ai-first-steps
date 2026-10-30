# 02 — Быстрый старт на Windows 10/11 (от пустой папки до MP4)

Ветка `arena/750486c0-ai-first-steps` самодостаточна — `main` не нужен.

## 0. Выбери папку

Проводник → диск с >10ГБ свободно → создай `D:\Projects` или `C:\Projects_arena`.

**Не используй** пробелы/кириллицу: `D:\Мои документы\AI проект\` сломает `ffmpeg`.

## 1. Поставь 2 программы

**Git:** https://git-scm.com/download/win → по умолчанию → перезапуск.

Проверка `Win+R` → `cmd` →:
```
git --version   # → git version 2.xx
node -v         # → v20.xx (если v24 — см. Troubleshooting 08)
npm -v          # → 10.xx
```

**Node.js 20 LTS:** https://nodejs.org → зелёная кнопка LTS (20.18). **Не ставь 24** — ломает `remotion browser ensure`. Если уже стоит 24 — удали через `Установка и удаление программ` и поставь 20.

**Python 3.11+** (только для FFmpeg-ветки и `build_timeline.py`): https://www.python.org/downloads/ → галочка `Add to PATH`.

Проверка:
```
python --version  # → Python 3.11+
pip --version
```

## 2. Скачай проект

Открой `D:\Projects` в Проводнике → клик в адресной строке → введи `cmd` → Enter.

Вставь **одну** строку:
```powershell
git clone --branch arena/750486c0-ai-first-steps https://github.com/Ovladimirovich/ai-first-steps.git
```

Проверка:
```powershell
dir ai-first-steps\remotion\src\pixarScenes   # → 26 файлов PS*.tsx
dir ai-first-steps\preview\pixar-why-ai-preview.mp4  # → 7.8МБ 6:18 уже готов
```

ZIP-альтернатива без git: https://github.com/Ovladimirovich/ai-first-steps/archive/refs/heads/arena/750486c0-ai-first-steps.zip → распаковать в `D:\Projects\ai-first-steps`.

## 3. Вариант A — Remotion (красивая веб-анимация, 50 мин)

```powershell
cd ai-first-steps\remotion
npm install                 # 1-2 мин, audited 209 packages
npx remotion browser ensure # должен написать Browser ensured, иначе см. 08
# проверка:
npx remotion studio src/index.ts  # http://localhost:3000 → выбери PixarWhyAI → Play → Ctrl+C для выхода

# финал 1080p
npx remotion render src/index.ts PixarWhyAI ../release/pixar-why-ai-full.mp4 --codec h264 --crf 18 --concurrency 4
# если OOM → --concurrency 2
# 720p быстрее:
npx remotion render src/index.ts PixarWhyAI ../release/pixar-why-ai-720.mp4 --codec h264 --crf 18 --concurrency 6 --scale 0.666666
```

Файл появится `..\release\pixar-why-ai-full.mp4` ~300МБ 6:19. Скопируй:
```powershell
copy ..\release\pixar-why-ai-full.mp4 ..\preview\
```

Если `No browser found` — укажи системный Chrome:
```powershell
npx remotion render src/index.ts PixarWhyAI ../release/pixar-why-ai-full.mp4 --codec h264 --crf 18 --concurrency 4 --browser-executable="C:\Program Files\Google\Chrome\Application\chrome.exe"
```

## 4. Вариант B — FFmpeg (быстрая склейка, 3-5 мин) — рекомендуется на твоём Xeon 8c/32ГБ

```powershell
cd C:\Projects_arena\ai-first-steps
pip install Pillow moviepy==1.0.3 imageio-ffmpeg

# финал 1080p как у Remotion но за 5 мин
python tools/build_ffmpeg_video.py --output release/pixar-why-ai-ffmpeg.mp4 --crf 18 --preset medium

# превью 720p за 1 мин
python tools/build_ffmpeg_video.py --preview --output preview/pixar-why-ai-ffmpeg-preview.mp4

# тест 10 реплик 20 сек без аудио
python tools/build_ffmpeg_video.py --only 10 --output C:\Temp\test.mp4 --no-audio --preset ultrafast
```

Логи показывают `сегментов: 114 (57 реплик + 57 пауз) суммарно 379.0s`. Файл `release/pixar-why-ai-ffmpeg.mp4` 26МБ 1920×1080 готов.

Оба варианта берут один `remotion/public/timing-pixar.json` + `remotion/public/audio/voice_track-pixar.mp3` — результат одинаковый по содержанию, разный по рендеру.

## 5. Оригинал «Первые шаги в ИИ» (30 сцен 11:45)

```powershell
cd ai-first-steps
python tools/build_timeline.py   # генерит timing.json + voice_track.mp3 + subtitles/ru.srt
cd remotion
npm install
npx remotion browser ensure
npm run render          # → ../release/final.mp4 1080p CRF26
npm run render:nosubs   # → ../release/final_nosubs.mp4 720p без subs
```

## 6. Что дальше

* Открой `release/*.mp4` в VLC, проверь звук на колонках класса.
* Хочешь править текст — см. `07_TIMELINE_VOICE.md` (меняешь `script/lines*.json` → перезапись mp3 → `build_timeline.py`).
* Хочешь новую сцену — скопируй `remotion/src/pixarScenes/PS1_2.tsx` → правь → `npm run dev` смотри вживую.
