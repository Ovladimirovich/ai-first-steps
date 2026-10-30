# Credits · «Первые шаги в ИИ» + Pixar «Зачем ИИ школьнику»
**Дата актуальности фактов:** 27 октября 2026 (оригинал) / 30 октября 2026 (Pixar) — см. `script/factcheck.md`.

## Инструменты

| Назначение | Инструмент | Лицензия |
|---|---|---|
| Анимация и рендер (оригинал + Pixar Remotion) | Remotion 4.0.300 (React/TS), `@sparticuz/chromium` 153 в песочнице | Remotion License (бесплатно физлицам/командам ≤3 чел.) |
| Быстрый рендер Pixar | Python 3.11 + **Pillow** + **MoviePy 1.0.3** + **imageio-ffmpeg** (`tools/build_ffmpeg_video.py`) | MIT / BSD |
| Озвучка | Нейросетевой TTS 2 голоса: Бит `voice-00`, Маша `voice-01` (57 Pixar + 85 оригинал) | по условиям TTS-провайдера |
| Таймлайн/субтитры | `tools/build_timeline.py`, `build_pixar_real_timeline.py` (ffprobe) + разбивка ≤42×2 | MIT |
| Звук | **ffmpeg** (imageio-ffmpeg), `loudnorm` EBU R128, `sidechaincompress` дакинг | LGPL/GPL |
| Фоновая музыка | Процедурная NumPy `assets/audio/music_ducked.mp3` + `voice_track*.mp3` concat | CC0 |
| Шрифты | Montserrat/Inter/DejaVu Sans + Noto Color Emoji | OFL |
| Персонажи/иконки/фоны SVG | Авторские в `remotion/src/components` и `pixarScenes/` (Bit/Masha/Pixel, 40 иконок, 5 фонов) | CC BY-NC 4.0 |
| Фоны Pixar JPG | AI-концепт `assets/pixar/classroom_pixar.jpg` 274К + `clouds_pixar_bg.jpg` 86К | CC0 / по условиям генератора |
| CI | GitHub Actions `ubuntu-latest` — `render-pixar.yml` (Node 20) + `render-ffmpeg.yml` (Python 3.11) | — |

## Товарные знаки

ChatGPT (OpenAI), Алиса / Alice AI (Яндекс), GigaChat и Kandinsky (Сбер) — товарные знаки владельцев. Логотипы не используются; названия в информационно-образовательных целях.

## Источники фактов

Перечислены в `script/factcheck.md` с датами публикаций. Для Pixar-версии блок 4 и 7 сверены на 30.10.2026 — укажи дату в титрах `PS8_2`.

## Благодарности

* Remotion команде за `Studio` и `browser ensure`
* MoviePy/Pillow за быстрый тракт 3-5 мин vs 50 мин Chrome
* GitHub за free Actions (2000 мин/мес)
