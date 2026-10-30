# 08 — Troubleshooting

## `No browser found for rendering frames` / `should have downloaded browser`

**Причина:** `Node 24` + Remotion 4.0.300 не качает `Chrome Headless Shell`.

**Решение:**
```powershell
# 1. Проверь версию
node -v   # если v24 → удали и поставь 20 LTS https://nodejs.org/dist/v20.18.0/node-v20.18.0-x64.msi
# 2. Переустанови
cd remotion
rmdir /s /q node_modules
npm install
npx remotion browser ensure   # должен написать Browser ensured
# 3. Если всё ещё падает — укажи системный Chrome:
npx remotion render src/index.ts PixarWhyAI ../release/pixar-why-ai-full.mp4 --codec h264 --crf 18 --concurrency 4 --browser-executable="C:\Program Files\Google\Chrome\Application\chrome.exe"
# Edge:
# --browser-executable="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
```

## `libnspr4.so: cannot open` / `/tmp/chromium` 127 (только песочница Arena)

```
LD_LIBRARY_PATH=/tmp/al2023/lib:/tmp:$LD_LIBRARY_PATH FONTCONFIG_PATH=/tmp/fonts HOME=/tmp npx remotion render ... --browser-executable=/tmp/chromium
```

Локально на Windows не нужно — Remotion сам качает Chrome.

## `Out of memory` / `JavaScript heap`

Снизь `--concurrency`:
```powershell
npx remotion render ... --concurrency 2  # вместо 4-6
# или рендер чанками:
bash tools/render_pixar_chunks.sh pixar-why-ai-full.mp4  # Linux
python tools/build_ffmpeg_video.py --output release/pixar-why-ai-ffmpeg.mp4  # 3 мин, 500МБ RAM
```

## `ENOSPC` / нет места

Нужно 3ГБ свободно. Очисти `release/`, `%TEMP%`, `C:\Users\...\AppData\Local\Temp`.

## Путь с кириллицей/пробелами

```
C:\Мои документы\AI проект\  → сломает ffmpeg
D:\Projects\ai-first-steps\ → ок
```

## Антивирус блочит Chrome

Разреши `C:\Users\...\AppData\Local\remotion\chrome-headless-shell-*` в исключениях Windows Defender.

## `externally-managed-environment` (pip на Linux)

```bash
pip install --break-system-packages -q Pillow moviepy==1.0.3 imageio-ffmpeg
# или venv:
python3 -m venv .venv && source .venv/bin/activate && pip install Pillow moviepy
```

## `ffprobe: command not found` (проверка)

`imageio-ffmpeg` уже ставит ffmpeg, но для `ffprobe` в `build_timeline.py` нужен системный:
```powershell
winget install Gyan.FFmpeg
# или choco install ffmpeg
```

## Рендер виснет на `Bundling 65%`

Подожди 2-3 мин — первый бандл долгий. Если >10 мин — `Ctrl+C` → `rmdir /s /q node_modules\.cache` → `npm install` снова.

## GitHub Actions `artifact not found`

`release/pixar-*.mp4` 26-300МБ < лимита 500МБ, но хранится 7 дней. Если `if-no-files-found: error` — смотри логи шага `Render …`, качай `debug-preview`.

## Как спросить помощь

Скинь:
```
node -v
npm -v
python --version
dir remotion\public\timing-pixar.json
npx remotion browser ensure --log verbose   # последние 20 строк
```
