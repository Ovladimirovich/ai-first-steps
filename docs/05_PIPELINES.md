# 05 — Тракты рендера: Remotion vs FFmpeg

## Зачем два тракта

* **Remotion** идеален для сложной веб-анимации (пружинки, градиенты, тени, `spring`, `interpolate`). Но он **рисует 11 550 веб-страниц в Chrome** — 50 мин.
* **FFmpeg/MoviePy** идеален для склейки готовых кусков (картинка + аудио + текст). Он **копирует потоки на C++** — 3-5 мин, в 10-20 раз быстрее.

Оба берут один `timing-pixar.json 379с` + `voice_track-pixar.mp3`. Выбирай по задаче.

## Сравнение честно

|  | Remotion `PixarWhyAI` | FFmpeg `build_ffmpeg_video.py` |
|---|---|---|
| Что делает | `React → HTML → Chrome Headless → png 1920x1080 30fps 11550 кадров → ffmpeg libx264` | `Pillow рисует 114 png 1920x1080 (карточка + текст) → MoviePy concat → ffmpeg libx264 + mux aac` |
| Время на Xeon 8c/16t 32ГБ | **50 мин 1 поток / 20 мин 4 потока** (`--concurrency 4`) | **5:18 medium / 3:00 ultrafast** (`--preset medium/ultrafast`) |
| Время на GitHub Actions (2 ядра) | ~60-80 мин | **~4 мин** |
| Зависимости | Node 20, Chrome Headless (~200МБ), `@sparticuz/chromium` в песочнице | Python 3.11, `Pillow + moviepy==1.0.3 + imageio-ffmpeg` (~50МБ), без Chrome/Node |
| Плюсы | Любая веб-красота, `PixarCard` с бликом/тенью/пружинкой за 10 строк, live Studio превью, точная вёрстка | Скорость, работает везде (Win/Linux), не ломается на `Node 24`, не нужен браузер, 0 OOM |
| Минусы | Долго, жрёт RAM (~300МБ на поток), ломается на `Node 24` (`No browser found`), нужен `browser ensure`, антивирус может блочить Chrome | Надо переписывать анимацию с TSX на Pillow (сейчас 114 статичных карточек, без `spring`), нет live Studio — только `still` картинки |
| Когда брать | Надо показать плавную анимацию, градиенты, физику иконок, интерактив | Надо быстро сдать финал, дедлайн, слабый ПК, облако, много правок текста |
| Команды | `cd remotion && npx remotion render src/index.ts PixarWhyAI ../release/pixar-why-ai-full.mp4 --crf 18 --concurrency 4` | `python tools/build_ffmpeg_video.py --output release/pixar-why-ai-ffmpeg.mp4 --crf 18 --preset medium` |
| Артефакты | `release/pixar-why-ai-full.mp4` ~300МБ | `release/pixar-why-ai-ffmpeg.mp4` 26МБ (medium) / `preview/*` 7.8МБ превью |

## Что уже есть в репозитории

* **Remotion:** 25 сцен `pixarScenes/PS*.tsx` + `PixarMain.tsx` + `timing-pixar.json 379с 57 cue` + `voice_track-pixar.mp3 2.9МБ` + чанки `tools/render_pixar_chunks.sh` (по 1500 кадров, докачка) + cloud `render-pixar.yml`
* **FFmpeg:** `tools/build_ffmpeg_video.py` (114 сегментов: 57 реплик + 57 пауз, Pillow `draw_pixar_image` с `P.bg #FFF6E0` + `PixarCard #243A66` + аватар `B/M` + `wrap_text` 40px + `clouds_pixar_bg.jpg` 0.18) + cloud `render-ffmpeg.yml` (ultrafast 4 мин)

## Гибрид (рекомендуем)

1. **Разработка** — в `Remotion Studio` (`npm run dev` → `PixarWhyAI` → `Play`) — смотри анимацию, правь `PS*.tsx`.
2. **Сдача** — `FFmpeg` (`python tools/build_ffmpeg_video.py`) — быстро собирай финал из тех же таймингов/голоса, пока Remotion рендерит ночь.

Если захочешь `spring` в FFmpeg — добавим `interpolate` через `Pillow` кадры (на каждую реплику 30 кадров с `translateY`/`scale`) — будет чуть медленнее (7 мин) но с анимацией.

## Как воспроизвести наш замер

Песочница Debian 12, `moviepy 1.0.3`:
```
FFmpeg 1920x1080 379.0s 114 segments → Pillow 114 png (1-2с) → Audio 8348 chunks → Video 11357 frames
medium crf18 threads4 → 5:18, 26МБ, 378.6s 30fps
ultrafast crf18 → ~3:00, ~22МБ
Remotion 1920x1080 11550 frames crf18 concurrency1 → ~50 мин (чанками preview/chunks_pixar 1500к)
```

На твоём `Xeon E5-2650 v2 8c/32ГБ` FFmpeg будет ~3 мин ultrafast, Remotion ~20 мин с `--concurrency 4`.

### Конструктор новых тем

```bash
python tools/new_topic.py "Зачем математика в 5 классе" --scenes 5
# → script/lines_zachem-matematika-v-5-klasse.json (57 реплик шаблон)
# → assets/audio/voice-zachem-matematika-v-5-klasse/ (папка для TTS)
# → script/scenario_zachem-matematika-v-5-klasse.md
# далее:
python tools/build_pixar_real_timeline.py --lines script/lines_zachem-matematika-v-5-klasse.json --voice assets/audio/voice-zachem-matematika-v-5-klasse --out remotion/public/timing-zachem-matematika-v-5-klasse.json
python tools/build_ffmpeg_video.py --motion 3 --use-workshop-bg --output release/zachem-matematika-v-5-klasse_motion.mp4 --crf 18 --preset medium
```

Пер-сценные фоны: положи `assets/pixar/scene_1.1.jpg` … `scene_8.2.jpg` 1920×1080 — подхватятся автоматом. Персонажи `bit.png`/`masha.png` 400×400 PNG с прозрачностью — наложатся с `parallax` (Бит покачивается).
