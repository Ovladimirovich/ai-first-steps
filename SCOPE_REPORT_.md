Резюме проверки чек-листа smoke по Agnes cloud (Local ComfyUI 0.34.5 ↔ Factory 7860):

✅ ПОДТВЕРЖДЕНО (UI + API + worker)
1. Настройки: save_settings → PATCH /api/settings, поля comfyui_* сохраняются. ✓
2. «Проверить Agnes-профиль»: GET /api/settings/comfyui/agnes-profile →
   {profile_id, available, quality[], aspect_ratios[], text_presets[], text_preset, missing_nodes[]}.
   UI форматирует строку «Профиль comfyui-agnes-t2i-v1 · качество: 1K, 2K, 4K · пропорции: … · preset: Prompt Enhance · workflow не запускался». ✓
3. «Сохранить prompt»: PATCH /api/projects/{id}/visuals/{sceneId} → visual.prompt.text. ✓
4. Чекбокс «Соглашаюсь…» → data-agnes-consent; при unchecked кнопка [data-generate-agnes-image] отключается. ✓
5. image-run с {max_cost:0, currency:"EUR", privacy_scope:"cloud_free", consent:true, cloud_consent:true} →
   pipeline.py.run: privacy_scope=="cloud_free" ∧ cloud_consent is True ∧ consent is True ∧ currency=="EUR" ∧ max_cost==0.0 → 202. ✓
6. Worker: _make_agnes_image_variant → create_visual_variant(source="generated", provenance="comfyui_agnes_txt2img", state="created"). ✓
7. Вариант не выбирается автоматически: select требует ручного POST /select с expected_revision. ✓
8. selectVisualVariant в app.js: PATCH/POST /visual-variants/{id}/select с expected_revision. ✓

🔧 ОДНО РАСХОЖДЕНИЕ в e2e-драйвере (factory_e2e_driver.py)

Функция cloud_free_quota_confirmation() отправляет privacy_scope: "cloud", а бэкенд (pipeline.py run) требует
privacy_scope: "cloud_free". При вызове image-run драйвер получает ValueError:
  «Для Agnes-облака требуется подтверждение cloud_free с отдельным облачным согласием»
→ Драйвер не сможет запустить image-run для Agnes-профиля.

ФИКС ДЛЯ e2e/factory_e2e_driver.py (строка ~96):
  "privacy_scope": "cloud",   →   "privacy_scope": "cloud_free",

Отдельные negative-кейсы (без согласия, превышение лимита, drift, COMFYUI недоступен, cancel) —
на стороне сервера валидируются в pipeline.run / jobs.py worker / comfyui.normalize_comfyui_base_url.
Затеннологированного доступа к API-ключу сервером не выявлено: драйвер только POST в локальный ComfyUI
через loopback 127.0.0.1, ключ живёт в настройках ComfyUI. ✓