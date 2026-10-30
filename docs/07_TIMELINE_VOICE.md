# 07 — Таймлайн, озвучка, субтитры

## Единый источник — `lines*.json`

Оригинал `script/lines.json` 85 реплик, Pixar `script/lines_pixar_why_ai.json` 57 реплик:

```json
{
  "id": "p1_2_b_02",
  "scene": "1.2",
  "who": "b",           // b=Бит (мужской), m=Маша (девочка)
  "text": "Вот фишка — попроси ИИ объяснить как для друга..."
}
```

Имя mp3 строго `s<сцена>_<who>_<n>.mp3` для оригинала и `p<блок>_<сц>_<who>_<n>.mp3` для Pixar — по `id`.

## Генерация тайминга

### Оригинал (реальный)
```bash
python tools/build_timeline.py
# читает assets/audio/voice/*.mp3 через ffprobe → dur
# генерит: remotion/public/timing.json (total 695с), voice_track.mp3 (concat), subtitles/ru.srt, music_ducked.mp3
```

### Pixar (два режима)

**Эмуляция без mp3** (до записи):
```bash
python tools/build_pixar_timing.py
# оценивает dur = len(text)*0.06*2.05 + 0.8с, генерит timing-pixar.json 547с (оценка), srt 8.5К
```

**Реальный после записи/TTS** (как сейчас):
```bash
# 1. Сгенерил 57 mp3 через TTS (voice-00 Bit, voice-01 Masha) → assets/audio/voice-pixar/
# 2. Склейка:
python tools/build_pixar_real_timeline.py
# читает 57 mp3 ffprobe → реальный timing-pixar.json 379.0с 71 cue (57 lines) + voice_track-pixar.mp3 2.9МБ + ru-pixar.srt
```

Разбивка длинных фраз: `cues` делит `lines` по пунктуации `, — .` чтобы субтитры ≤42×2 строк, синхрон ±100мс.

## Как заменить реплику

1. Правь текст в `script/scenario_why_ai_pixar.md` и `script/lines_pixar_why_ai.json`
2. Перезапиши `assets/audio/voice-pixar/<id>.mp3` (TTS: `python -m elevenlab` или вручную)
3. Перегенери `python tools/build_pixar_real_timeline.py` → `timing-pixar.json` + `voice_track-pixar.mp3` + `srt`
4. Перерендери `python tools/build_ffmpeg_video.py` (3 мин) или `npx remotion render` (50 мин)

Границы сцен сдвинутся автоматически — руками `timing` не правь.

## Voice_track

* Оригинал: `remotion/public/audio/voice_track.mp3` 5.4М 695с (85 mp3 + 6с хвост)
* Pixar: `remotion/public/audio/voice_track-pixar.mp3` 2.9М 379с (57 mp3 + 6с хвост) — моно 48kHz, `ffmpeg -f concat`

В `PixarMain.tsx`:
```tsx
<Audio src={staticFile("audio/voice_track-pixar.mp3")} />
```
В FFmpeg:
```python
audio = AudioFileClip("remotion/public/audio/voice_track-pixar.mp3").subclip(0, final.duration)
final.set_audio(audio)
```

## Субтитры

* `subtitles/ru.srt` и `ru-pixar.srt` — `≤42 символа ×2 строки, ≥1с показ`
* В Remotion — `<Subtitle>` с `timing.cues`, вшивается при рендере (`--props='{"subs":true}'`)
* В FFmpeg превью — burned через `ffmpeg -vf subtitles=ru-pixar.srt:fontsdir=/usr/share/fonts:force_style='FontName=DejaVu Sans,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H90000000,BorderStyle=3,Outline=2,Shadow=0,MarginV=28,Alignment=2'`

## Проверка

```bash
cat remotion/public/timing-pixar.json | python -c "import json; j=json.load(open('remotion/public/timing-pixar.json')); print(f\"total={j['total']}s cues={len(j['lines'])} lines={len(j['lines'])}\")"
ffprobe -v error -show_format -show_streams remotion/public/audio/voice_track-pixar.mp3 | grep duration
# должно совпасть с total
```
