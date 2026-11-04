# Работа со своими кадрами, эскизами и фонами

**Проект:** ai-first-steps  
**Корень:** `C:\Projects_arena\ai-first-steps`  
**Ветка:** `arena/9d50668a-ai-first-steps`  
**Назначение:** подробное руководство по интеграции собственных изображений, скетчей, фонов и начальных кадров в обучающие ролики.

---

## 1. Что можно использовать

Вы можете загрузить в проект практически любые растровые и векторные изображения, а также видеозаставки.

| Тип файла | Расширения | Для чего подходит |
|-----------|------------|-------------------|
| Фоновое изображение | `.jpg`, `.jpeg`, `.png`, `.webp` | Мастерская, класс, небо, интерьер, главное полотно за персонажем |
| Скетч / эскиз персонажа | `.png` (с прозрачностью), `.webp`, `.svg` | Персонаж, предмет, иконка, объект поверх фона |
| Видео-заставка (initial frame) | `.mp4`, `.webm` | Заставка в начале ролика, анимированный intro |
| Спрайт-лист персонажа | `.png`, `.jpg` | Анимация движущегося героя (ходьба, жесты, говорение) |
| Аудио (озвучка) | `.mp3`, `.wav` | Голос персонажей, музыка, фоновый шум |

> **Рекомендация:** фоны лучше готовить размером **1920×1080** (Full HD). Если изображение больше — Remotion уменьшит его, но размер файла ролика вырастет. Если меньше — появится размытие или чёрные поля.

---

## 2. Где хранить файлы

Все исходные ассеты хранятся в папке `assets/`. Для рендера через Remotion файлы дублируются в `remotion/public/`, потому что браузер (Chrome) при рендере видит только содержимое `public/`.

```
C:\Projects_arena\ai-first-steps\
├── assets\                              # ← ИСТОЧНИКИ (ваши оригиналы)
│   ├── pixar\                           # ваши фоны, скетчи, иллюстрации
│   │   ├── my-background.jpg
│   │   ├── character-sketch.png
│   │   └── intro-sprite.png
│   └── audio\                           # ваша озвучка
│       └── voice-track.mp3
├── remotion\                            # Remotion проект (Node.js)
│   ├── public\                          # ← КОПИИ для рендера (браузер видит только это)
│   │   ├── pixar\
│   │   │   ├── my-background.jpg        # ← скопировать из assets\pixar\
│   │   │   └── character-sketch.png     # ← скопировать из assets\pixar\
│   │   ├── audio\
│   │   │   └── voice-track.mp3          # ← скопировать из assets\audio\
│   │   └── timing-*.json
│   └── src\
│       ├── scenes\                      # ваши новые сцены (TSX)
│       └── index.ts                     # зарегистрировать композицию
├── tools\
│   └── build_ffmpeg_video.py            # быстрый тест через MoviePy
└── release\                             # готовые MP4
```

---

## 3. Практические задачи

### 3.1. Фон мастерской (1920×1080)

**Задача:** Вставить свой фон мастерской вместо родного `pixar-style-preview.jpg`.

**Шаги:**
1. Подготовьте картинку размером 1920×1080 (или близким размерам).
2. Положите её в `assets/pixar/my-workshop-bg.jpg`.
3. Скопируйте в `remotion/public/pixar/my-workshop-bg.jpg` (для Remotion).
4. Обновите `remotion/src/scenes/S0_1.tsx` или вашу сцену:

```tsx
import { staticFile, useVideoConfig } from "remotion";

export const WorkshopScene: React.FC = () => {
  const { width, height } = useVideoConfig();

  return (
    <div style={{
      width, height,
      background: `url(${staticFile("pixar/my-workshop-bg.jpg")}) center/cover no-repeat`,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      {/* контент поверх фона */}
    </div>
  );
};
```

5. Зарегистрируйте сцену в `remotion/src/scenes/index.tsx`.
6. Запустите рендер: `npx remotion render src/index.ts MyComposition release/my-topic.mp4`.

> Если фон лежит в `assets/pixar/`, для CSS-ссылок он будет доступен как `pixar/my-workshop-bg.jpg` в `remotion/public/`.

### 3.2. Персонаж или скетч поверх фона

**Задача:** Разместить скетч персонажа на фоне мастерской.

**Подготовка:**
- Скетч должен быть в PNG с прозрачным фоном.
- Размер скетча не важен — Remotion растянет/сожмёт до нужных размеров.

**Реализация:**

```tsx
import { staticFile } from "remotion";

export const CharacterSketch: React.FC = () => {
  return (
    <img
      src={staticFile("pixar/character-sketch.png")}
      style={{
        width: 400,
        height: 400,
        position: "absolute",
        bottom: 50,
        left: 100,
      }}
      alt="Персонаж"
    />
  );
};
```

> Если у скетча прозрачный фон (PNG), он будет виден поверх общего фона без лишнего прямоугольника.

### 3.3. Свой скетч / персонаж поверх фона

**Задача:** Комбинировать фон и скетч в одной сцене.

```tsx
import { staticFile, useVideoConfig } from "remotion";

export const MyScene: React.FC = () => {
  const { width, height } = useVideoConfig();

  return (
    <div style={{ width, height, position: "relative" }}>
      {/* Фон */}
      <div style={{
        width: "100%", height: "100%",
        background: `url(${staticFile("pixar/my-background.jpg")}) center/cover`,
      }} />

      {/* Скетч поверх */}
      <img
        src={staticFile("pixar/character-sketch.png")}
        style={{
          width: 300,
          height: 300,
          position: "absolute",
          bottom: 80,
          right: 100,
        }}
        alt="Персонаж"
      />
    </div>
  );
};
```

### 3.4. Анимация спрайт-листа (движущийся персонаж)

Если у вас есть спрайт-лист (ряд кадров персонажа в одном файле), используйте `<SpriteSheet>`:

```tsx
import { SpriteSheet, staticFile } from "remotion";

const sprite = staticFile("pixar/character-walk.png"); // например, 10 кадров в ряд

export const WalkingCharacter: React.FC = () => {
  return (
    <SpriteSheet
      src={sprite}
      cols={10}              // количество кадров в ряду
      count={10}             // всего кадров
      fps={30}
      width={400}
      height={400}
      playCount={Infinity}   // зациклить анимацию
    />
  );
};
```

### 3.5. Начальные кадры / initial frame (заставка)

Чтобы ролик начинался с вашего скетча на несколько секунд, создайте сцену только с картинкой и задайте длительность:

```tsx
import { Sequence, staticFile, useVideoConfig } from "remotion";

export const IntroScene: React.FC = () => {
  const { width, height } = useVideoConfig();

  return (
    <div style={{
      width, height,
      background: `url(${staticFile("pixar/intro-sketch.jpg")}) center/cover`,
    }}>
      <h1 style={{ color: "#fff", fontSize: 60 }}>Моя обучающая тема</h1>
    </div>
  );
};

// В composição:
// <Sequence from={0} durationInFrames={90} name="Intro">
//   <IntroScene />
// </Sequence>
```

### 3.6. Пример полной сцены с фоном и текстом

```tsx
import { Sequence, staticFile, useVideoConfig } from "remotion";

export const MyTopicScene: React.FC<{ text: string }> = ({ text }) => {
  const { width, height } = useVideoConfig();

  return (
    <div style={{ width, height, position: "relative" }}>
      {/* Фон */}
      <div style={{
        width: "100%", height: "100%",
        background: `url(${staticFile("pixar/my-background.jpg")}) center/cover`,
      }} />

      {/* Текстовая карточка поверх */}
      <div style={{
        position: "absolute", bottom: 120, left: 80,
        width: 700, background: "#243A66", color: "#fff",
        padding: 24, borderRadius: 12,
        boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
      }}>
        <h2 style={{ margin: 0, fontSize: 32 }}>{text}</h2>
      </div>
    </div>
  );
};
```

---

## 3.7. Чек-лист интеграции (от загрузки файла до готового ролика)

Этот чек-лист показывает полный рабочий процесс от получения файла до готового ролика.

**ЭТАП 1. Подготовка файла**
- [ ] Файл выбран и подтверждён тип (изображение/видео/аудио/спрайт)
- [ ] Размер соответствует требованиям (1920×1080 для фонов; PNG для прозрачных скетчей)
- [ ] Файл переименован по соглашению: `bg_1920x1080.jpg`, `char_sketch_v1.png`, `intro.mp4`
- [ ] Файл скачан в `assets/pixar/` (изображения/скетчи) или `assets/audio/`

**ЭТАП 2. Копирование для Remotion**
- [ ] Копия файла создана в `remotion/public/pixar/` (для изображений/скетчей)
- [ ] Копия файла создана в `remotion/public/audio/` (для озвучки)
- [ ] Имена совпадают в обеих папках

**ЭТАП 3. Создание сцены**
- [ ] Сцена создана в `remotion/src/scenes/` (для новых тем)
- [ ] Сцена использует `staticFile()` для ссылки на ассет
- [ ] Сцена корректно экспортируется в `remotion/src/scenes/index.tsx`

**ЭТАП 4. Регистрация в проекте**
- [ ] Сцена зарегистрирована в `remotion/src/index.ts`
- [ ] `npx tsc --noEmit` → 0 ошибок

**ЭТАП 5. Быстрый тест (MoviePy)**
- [ ] `python tools/build_ffmpeg_video.py --only 2 --motion 3 --use-workshop-bg --output C:\Temp\test.mp4`
- [ ] Результат проверён визуально (фон, текст, анимация)

**ЭТАП 6. Полный рендер (Remotion)**
- [ ] `npx remotion render src/index.ts MyComposition ../release/my-topic.mp4 --codec h264`
- [ ] Рендер успешно завершён, файл в `release/`

**ЭТАП 7. Проверка и распространение**
- [ ] Превью скопировано в `preview/`
- [ ] Файл протестирован (проигран, звук, текст)
- [ ] Скриншоты удачных кадров сохранены для отчёта

---

## 4. Разработка новой темы в 15 минут

### 4.1. Скопируйте базовую сцену
Скопируйте `remotion/src/scenes/S0_1.tsx` в `remotion/src/scenes/SNew.tsx` и измените название композиции.

### 4.2. Подключите свой фон
Замените `staticFile("pixar/classroom_pixar.jpg")` на свой файл `staticFile("pixar/my-bg.jpg")`.

### 4.3. Зарегистрируйте сцену
Добавьте экспорт в `remotion/src/scenes/index.tsx`:

```tsx
export { MyNewScene } from "./SNew";
```

### 4.4. Добавьте в корневой список
Поправьте `remotion/src/index.ts`, чтобы зарегистрировать новую композицию.

### 4.5. Проверьте локально
Запустите: `npx remotion studio` — откроется preview-окно.

### 4.6. Сделайте рендер
`npx remotion render src/index.ts MyNewComposition release/my-topic.mp4`.

### 4.7. Поделитесь превью
Скопируйте файл из `release/` в `preview/`.

---

## 5. Удаление двойников

Когда вы загружаете свои ассеты, не создавайте дубликаты:

- ❌ Не кладите копию фона в `assets/pixar/` **и** в `remotion/public/pixar/` с одними и теми же именами.
- ✅ Кладёте исходник в `assets/` и только копию для `remotion/public/`.
- ❌ Не создавайте множество версий одного скетча (например, `sketch1.png`, `sketch2.png`).
- ✅ Используйте только одну версию файла и при необходимости делайте ресайз в скриптах.

---

## 6. Конкретные сценарии (таблица)

| Что хотите сделать | Решение | Инструмент | Пример файла |
|-------------------|---------|------------|--------------|
| Свой фон мастерской | `staticFile("pixar/my-bg.jpg")` в CSS `background` | Remotion | `assets/pixar/my-bg.jpg` |
| Свой скетч персонажа | `src={staticFile("pixar/sketch.png")}` | Remotion | `assets/pixar/sketch.png` |
| Анимированный герой | `<SpriteSheet>` из спрайт-листа | Remotion | `assets/pixar/hero-sprite.png` |
| Заставка в начале | Сцена только с картинкой, `durationInFrames=90` | Remotion | `assets/pixar/intro.jpg` |
| Быстрый тест со своим фоном | Изменить `bg_path` в `build_ffmpeg_video.py` | MoviePy | `assets/pixar/test-bg.jpg` |
| Своя озвучка | `staticFile("audio/my-voice.mp3")` в `<Audio>` | Remotion | `assets/audio/my-voice.mp3` |

---

## 7. Ограничения и решения

| Проблема | Причина | Решение |
|----------|---------|---------|
| Картинка не отображается при рендере | Файл лежит в `assets/`, но не в `remoti` | Скопируйте файл в `remotion/public/pixar/` |
| Chrome кэширует старую картинку | Браузер не видит изменения | Переименуйте файл или очистите кэш |
| Большой PNG (>5 МБ) вызывает OOM | Chrome не тянет тяжёлый файл | Конвертируйте в JPEG или WebP |
| Прозрачность не работает | Используется JPG вместо PNG | Сохраняйте скетчи с прозрачным фоном в PNG |
| Аудио не играет | Формат не MP3 или файл не в `public/audio/` | Конвертируйте в MP3 и положите в `assets/audio/`, скопируйте в `remotion/public/audio/` |
| PowerShell `&&` не работает | Ограничение оболочки | Используйте `;` вместо `&&` |

---

## 8. Готовые примеры в проекте (что можно заменить)

| Файл в проекте | Что это | Куда вставить своё |
|----------------|---------|---------------------|
| `assets/pixar/classroom_pixar.jpg` | Фон класса | Свой класс / кабинет |
| `assets/pixar/clouds_pixar_bg.jpg` | Фон с облаками | Свой небный фон |
| `pixar-style-preview.jpg` | Фон мастерской (Бит + Маша) | Своя мастерская / офис |
| `remotion/src/pixarScenes/PS0_2.tsx` | Сцена с фоном `clouds_pixar_bg.jpg` | Вставьте свой фон |
| `remotion/public/audio/voice_track-pixar.mp3` | Озвучка Pixar-ролика | Ваша озвучка |

---

## 9. Чек-лист перед рендером нового ролика со своим контентом

- [ ] Исходник лежит в `assets/pixar/` (или `assets/audio/`)
- [ ] Копия скопирована в `remotion/public/pixar/` (для Remotion)
- [ ] Сцена создана в `remotion/src/scenes/` или `remotion/src/pixarScenes/`
- [ ] Сцена экспортирована в `remotion/src/scenes/index.tsx` или `pixarScenes/index.tsx`
- [ ] Composição зарегистрирована в `remotion/src/index.ts`
- [ ] `npx tsc --noEmit` → 0 ошибок
- [ ] Тестовый рендер MoviePy прошёл (`C:\Temp\test-*.mp4`)
- [ ] Полный рендер Remotion прошёл (`release/*.mp4`)
- [ ] Превью скопировано в `preview/`

---

## 10. Быстрая шпаргалка (команды)

```powershell
# 1. Скопировать свой фон в public
copy "C:\Projects_arena\ai-first-steps\assets\pixar\my-bg.jpg" "C:\Projects_arena\ai-first-steps\remotion\public\pixar\my-bg.jpg"

# 2. Проверить TypeScript
cd C:\Projects_arena\ai-first-steps\remotion
npx tsc --noEmit

# 3. Быстрый тест (MoviePy)
cd C:\Projects_arena\ai-first-steps
python tools/build_ffmpeg_video.py --only 2 --motion 3 --use-workshop-bg --output "C:\Temp\test.mp4"

# 4. Полный рендер (Remotion)
cd remotion
npx remotion render src/index.ts MyComposition ../release/my-topic.mp4 --codec h264

# 5. Превью
copy C:\Projects_arena\ai-first-steps\release\my-topic.mp4 C:\Projects_arena\ai-first-steps\preview\my-topic-preview.mp4
```

---

*Документ предназначен для autonomous-работы. Если что-то не получается — проверьте раздел «Ограничения и решения» или откройте issue в GitHub.*
