Резюме проверки чек-листа smoke — локальный рендер ролика (без Agnes/ComfyUI):

✅ ПОДТВЕРЖДЕНО (API + worker + pipeline)

1. Настройки: save_settings → PATCH /api/settings, поля comfyui_* сохраняются. ✓
2. «Проверить Agnes-профиль»: GET /api/settings/comfyui/agnes-profile →
   {profile_id, available, quality[], aspect_ratios[], text_presets[], text_preset, missing_nodes[]}. ✓
3. «Сохранить prompt»: PATCH /api/projects/{id}/visuals/{sceneId} → visual.prompt.text. ✓
4. Visual variants: POST /api/projects/{id}/visual-variants (загрузка существующих
   фонов из active-scene-backgrounds/), затем review + select. ✓
5. Голос: voice-plan + voice-run (piper, local). ✓
6. Кадры: frames-plan + frames-run (local). ✓
7. Рендер: render-plan + render-run → final.mp4 на диске. ✓

🔧 ИСПРАВЛЕНИЯ в этой ветке (fix/agnes-cloud-free-smoke-test)

factory/pipeline.py:
  - _run_cancellable задаёт TQDM_DISABLE=1 и PYTHONUNBUFFERED=1 для дочерних
    процессов — устраняет дедлок рендера на ~81% из помощью tqdm \r без \n,
    который заполняет OS pipe-буфер.

factory/storage.py:
  - atomic_write_json пробует атомарную запись через temp + os.replace.
  - Только при PermissionError на Windows — прямая запись (fallback).
  - Временный файл очищается в обоих случаях.

factory/comfyui_profiles.py:
  - COMBO-входы ComfyUI: опции читаются из definition[1]["options"],
    а не только из definition[0].

tools/build_ffmpeg_video.py:
  - moviepy 2.x импорты (from moviepy import ...) с fallback на 1.x.
  - Совместимые обёртки _subclip/_set_audio/_set_duration для subclip→subclipped,
    set_audio→with_audio, set_duration→with_duration.

e2e/factory_e2e_driver.py:
  - Пропускает Agnes/ComfyUI генерацию изображений; загружает готовые фоны
    из .factory/projects/<id>/active-scene-backgrounds/ как visual variants.
  - При пустом сценарии завершается ошибкой (не тратит облачный квоту на
    script-draft с privacy_scope: "cloud" и лимитом 500 RUB).
  - UTF-8 консоль на Windows (reconfigure + fallback на cp1251).
  - cloud_free_quota_confirmation использует privacy_scope: "cloud_free".

Отдельные negative-кейсы (без согласия, превышение лимита, drift, COMFYUI недоступен, cancel)
— на стороне сервера валидируются в pipeline.run / jobs.py worker / comfyui.normalize_comfyui_base_url.
