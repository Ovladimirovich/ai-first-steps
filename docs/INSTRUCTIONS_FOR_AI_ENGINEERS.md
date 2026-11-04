# Инструкции для ИИ-инженеров: автономное создание обучающих ролликов

**Проект:** ai-first-steps  
**Ветка:** `arena/9d50668a-ai-first-steps`  
**Папка проекта:** `C:\Projects_arena\ai-first-steps`  
**Язык:** Russian

---

## 0. Быстрая справка (TL;DR)

| Задача | Команда |
|--------|---------|
| Переключиться на рабочую ветку | `git checkout arena/9d50668a-ai-first-steps` |
| Проверить окружение | `node -v` (должно быть 20 LTS), `python --version` (3.11+) |
| Установить зависимости | `cd remotion && npm install` + `pip install Pillow moviepy==1.0.3 imageio-ffmpeg numpy` |
| Собрать тест (2 реплики, без аудио) | `python tools/build_ffmpeg_video.py --only 2 --motion 3 --use-workshop-bg --output C:\Temp\test.mp4 --preset ultrafast --no-audio` |
| Отрендерить полное видео (Remotion) | `npx remotion render src/index.ts <CompName> ../release/<тема>.mp4 --codec h264 --crf 18 --concurrency 4 --browser-executable="C:\Program Files\Google\Chrome\Application\chrome.exe"` |

---

## 8. Автоматизация (для ИИ-инженеров)

Можно скриптовать создание новой темы:

```python
# Пример: generate_topic.py
import json, os, shutil

def create_topic(topic_name: str, lines: list, total_seconds: float):
    root = r"C:\Projects_arena\ai-first-steps"
    
    # 1. Тайминг
    timing = {"fps": 30, "total": total_seconds, "lines": lines, "cues": []}
    with open(f"{root}/remotion/public/timing-{topic_name}.json", "w", encoding="utf-8") as f:
        json.dump(timing, f, ensure_ascii=False, indent=2)
    
    # 2. Папка сцен
    os.makedirs(f"{root}/remotion/src/scenes/{topic_name}", exist_ok=True)
    
    # 3. ... создать index.tsx, ВашаТемаMain.tsx, обновить index.ts
```

---

## 9. Контакты и ссылки

- **Remotion docs:** https://www.remotion.dev/
- **FFmpeg:** https://ffmpeg.org/
- **Node 20 LTS:** https://nodejs.org/
- **Проект:** `C:\Projects_arena\ai-first-steps`

---

*Инструкция составлена для автономной работы ИИ-инженеров. Обновляйте её при изменении конвейера.*
## 6. Чек-лист перед коммитом новой темы

- [ ] Ветка синхронизирована с `arena/9d50668a-ai-first-steps`
- [ ] `timing-<тема>.json` валидный JSON
- [ ] `voice_track-<тема>.mp3` лежит в `remotion/public/audio/`
- [ ] Новые сцены в `remotion/src/scenes/<тема>/`
- [ ] Composição экспортирована в `remotion/src/index.ts`
- [ ] `npx tsc --noEmit` → 0 ошибок
- [ ] Тестовый рендер MoviePy прошёл (проверьте `C:\Temp\test_*.mp4`)
- [ ] Полный рендер Remotion прошёл (проверьте `release\*.mp4`)
- [ ] Превью скопировано в `preview\`

---

## 7. Распространённые проблемы и решения

| Проблема | Решение |
|----------|---------|
| `No browser found` (Remotion) | Убедитесь, что Node 20 LTS и `--browser-executable="C:\Program Files\Google\Chrome\Application\chrome.exe"` |
| `Cannot find module '../public/timing.json'` | Скопируйте `timing-pixar.json` → `timing.json` или создайте свой `timing-<тема>.json` |
| `moviepy` ошибка импорта | `pip install --force-reinstall Pillow moviepy==1.0.3 imageio-ffmpeg numpy` |
| Pillow конфликт с gradio/streamlit | Поставьте `Pillow<13` (например, 12.3.0) — не критично для конвейера |
| OOM при рендере Remotion | Снизьте `--concurrency 4` до `--concurrency 2` |
| PowerShell `&&` не работает | Используйте `;` вместо `&&` |
| Ошибка `-c:v` в ffmpeg (MoviePy) | Баг в `build_ffmpeg_video.py` строка 598 — исправлен: `-i` добавляется только если есть аудио |

---
## 4. Два конвейера на выбор

| Критерий | Remotion (полный) | MoviePy + Pillow (быстрый) |
|----------|-------------------|----------------------------|
| Качество | Персонажи, анимация, переходы | Статичные карточки + бегущий текст |
| Сложность | Высокая (React + scènes) | Низкая (JSON + фон) |
| Время рендера | Долго (1–2 ч на 6–9 мин) | Быстро (мин на 12 с) |
| Когда использовать | Финальные обучающие ролики | Тесты, черновики, соцсети |
| Команда | `npx remotion render ...` | `python tools/build_ffmpeg_video.py ...` |

---

## 5. Параметры рендера (Remotion)

Обязательные флаги для Windows:
```powershell
--browser-executable="C:\Program Files\Google\Chrome\Application\chrome.exe"
--codec h264
--crf 18
--concurrency 4
```

Если OOM (нехватка памяти): `--concurrency 2`.

Выход: `../release/<имя>.mp4`.

---
## 3. Рабочий процесс создания новой темы (пошагово)

### Шаг 1. Создать ветку для темы (опционально, но рекомендуется)
```powershell
git checkout -b arena/<ваша-тема>
```

### Шаг 2. Подготовить тайминг и озвучку

Нужно два файла:

1. **`remotion/public/timing-<тема>.json`**
   ```json
   {
     "fps": 30,
     "total": 240.0,
     "lines": [
       {"who": "Бит", "text": "Привет, это новая тема", "scene": "0.1", "start": 0.0, "end": 4.5},
       {"who": "Маша", "text": "Второй реплик", "scene": "0.2", "start": 5.0, "end": 9.2}
     ],
     "cues": []
   }
   ```

2. **`remotion/public/audio/voice_track-<тема>.mp3`** — готовая озвучка.

> Совет: можно взять заготовку из `timing-pixar.json` и заменить текст/время.

### Шаг 3. Создать сцены (Remotion — полноценная анимация)

В папке `remotion/src/scenes/ваша_тема/` создайте файлы:

```
remotion/src/scenes/ваша_тема/
├── index.tsx          # экспортирует все сцены темы
├── S0_1.tsx           # сцена 0.1 — введение
├── S0_2.tsx           # сцена 0.2 — 4 суперсилы
├── S1_1.tsx           # сцена 1.1
├── ...
└── Placeholder.tsx    # заглушка для недоделанных сцен
```

Пример сцены (`S0_1.tsx`):
```tsx
import { Sequence } from "remotion";
import type { SceneProps } from ".";

export const S0_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  return (
    <div style={{ width: 1920, height: 1080, background: "#FFF6E0" }}>
      <h1>{lines[0]?.text}</h1>
    </div>
  );
};
```

### Шаг 4. Создать composição (точка входа для рендера)

Создайте `remotion/src/ВашаТемаMain.tsx`:
```tsx
import { Sequence } from "remotion";
import * as Scenes from "./scenes/ваша_тема";

export const ВашаТема: React.FC = () => {
  return (
    <Sequence from={0} durationInFrames={7200} name="Ваша тема">
      <Scenes.S0_1 lines={[]} sceneStart={0} />
      {/* добавьте остальные сцены */}
    </Sequence>
  );
};
```

Зарегистрируйте в `remotion/src/index.ts`:
```tsx
export { ВашаТема } from "./ВашаТемаMain";
```

### Шаг 5. Собрать тест (MoviePy — быстро, без полной анимации)
```powershell
python tools/build_ffmpeg_video.py --only 2 --motion 3 --use-workshop-bg --output C:\Temp\test_ваша_тема.mp4 --preset ultrafast --no-audio
```
Ожидаемый размер: ~5–6 МБ, длительность ~12.6 с.

### Шаг 6. Отрендерить полное видео (Remotion)
```powershell
cd C:\Projects_arena\ai-first-steps\remotion
npx remotion render src/index.ts ВашаТема ../release/ваша_тема.mp4 --codec h264 --crf 18 --concurrency 4 --browser-executable="C:\Program Files\Google\Chrome\Application\chrome.exe"
```

### Шаг 7. Скопировать превью
```powershell
copy C:\Projects_arena\ai-first-steps\release\ваша_тема.mp4 C:\Projects_arena\ai-first-steps\preview\ваша_тема-preview.mp4
```

---
## 2. Структура проекта

```
C:\Projects_arena\ai-first-steps\
├── remotion\
│   ├── src\
│   │   ├── index.ts                 # экспорты всех композиций
│   │   ├── Root.tsx                 # главная точка входа Remotion
│   │   ├── PixarMain.tsx            # пример composição PixarWhyAI
│   │   ├── pixarTheme.ts            # цветовая палитра Pixar
│   │   ├── components/              # переиспользуемые React-компоненты
│   │   ├── pixarScenes\             # 26 готовых сцен (PS0_1 … PS8_2)
│   │   └── scenes\                  # НОВЫЕ сцены для своих тем класть сюда
│   ├── public\
│   │   ├── timing-pixar.json        # таймкоды реплик (пример)
│   │   ├── timing-<тема>.json       # НОВЫЕ таймкоды для своей темы
│   │   └── audio\
│   │       ├── voice_track-pixar.mp3
│   │       └── voice_track-<тема>.mp3
│   └── package.json
├── tools\
│   └── build_ffmpeg_video.py        # быстрый рендер через MoviePy + Pillow
├── docs\                            # документация (этот файл здесь)
├── preview\                         # готовые превью
├── release\                         # финальные MP4
├── pixar-style-preview.jpg          # фон мастерской (Бит + Маша)
└── assets\                          # картинки, фоны, иконки
```

---
## 1. Окружение (проверка перед началом)

Выполнять в `C:\Projects_arena\ai-first-steps`.

### 1.1 Git
```powershell
git fetch origin
git checkout arena/9d50668a-ai-first-steps
git pull origin arena/9d50668a-ai-first-steps
git log --oneline -3
```

### 1.2 Node.js
- Требуется **Node 20 LTS** (v20.18.0 рекомендуется).
- Если установлен v24 — Remotion 4.0.300 сломается (`No browser found`).
- Проверка: `node -v` → должно быть `v20.x.x`.

### 1.3 Python
- Требуется **Python 3.11+** (установлен 3.14.3).
- Проверка: `python --version`.

### 1.4 Пакеты Python
Выполнять один раз:
```powershell
python -m pip install --upgrade pip
python -m pip install --force-reinstall Pillow moviepy==1.0.3 imageio-ffmpeg numpy
```
Проверка:
```powershell
python -c "import moviepy.editor; print('moviepy ok')"
python -c "import PIL; print('Pillow', PIL.__version__)"
```

### 1.5 Пакеты Node (Remotion)
```powershell
cd remotion
npm install
npx tsc --noEmit   # должно быть 0 ошибок
cd ..
```

---