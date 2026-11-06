# Отчёты локальной проверки

Здесь фиксируются проверки, которые нельзя воспроизвести в песочнице: Windows, локальный Piper, ComfyUI, GPU и субъективное качество изображений/речи. Это отчёт о фактах, а не источник секретов.

## Правила внесения отчётов

- Записывать commit, который действительно проверялся, и точные команды/действия.
- Отделять автоматические тесты от ручной оценки результата.
- Указывать только необходимые версии, имена профилей/моделей, длительности и ошибки.
- Не добавлять токены, `.env`, полные личные пути, `.factory/settings.json`, сами модели, WAV/MP4 и пользовательские проекты.
- Новые проверки добавлять отдельной датированной записью ниже; прежние записи не перезаписывать.

## 2026-11-05 — Piper preview, commit `cb3dcb9`

**Источник:** результаты ручной проверки пользователя на локальном Windows-компьютере; не запускалось из песочницы.

| Проверка | Результат |
|---|---|
| UI создаёт и отдаёт WAV-пробы `h1`/`h2` | Пройдено |
| `h1` | `ru_RU-dmitri-medium.onnx`, 24.83 с, файл 1,095,212 байт |
| `h2` | `ru_RU-irina-medium.onnx`, 28.42 с, файл 1,253,420 байт |
| Ручная оценка слышимой речи | Не пройдена: пользователь слышит неразборчивую речь («тарабарщина») |
| Piper принят для готовых роликов | Нет; требуется диагностика моделей/sidecar и сравнение локальных TTS |
| Проверка ComfyUI | Ещё не выполнялась |

Фактические WAV и модели локальны и в репозиторий не помещаются.

## 2026-11-06 — ComfyUI и Agnes API, уточнение пользователя

**Источник:** уточнение пользователя после отчёта локального инженера; не запускалось из Arena.

| Проверка/сведение | Результат |
|---|---|
| ComfyUI API на локальном компьютере | Доступен; ранее сообщены backend 0.34.5 и CPU-only PyTorch |
| Генерация локальными моделями | Пользователь подтверждает, что изображение было создано на CPU, но медленно; время/параметры конкретного запуска в этом уточнении не указаны |
| AgnesImage / AgnesText через API | Пользователь сообщает об успешном image-generation workflow через ComfyUI API с AgnesImage и AgnesText. В предоставленном примере AgnesImage является image-node, а AgnesText используется в агентном процессе создания визуального результата; точные связи выходов должны фиксироваться по реально запускавшемуся workflow. Проверялось пользователем/агентом, Arena повторно не запускал |
| Облачный маршрут Agnes | Пользователь подтверждает, что endpoint `https://apihub.agnes-ai.com/v1` и ключ настроены в ComfyUI и работают. По словам пользователя, сервис использует бесплатную, но ограниченную квоту, которой должно хватать проекту; числовой размер/условия квоты не записаны. Это облачный, не локальный инференс |
| Запросы/расходы со стороны Arena | Не выполнялись; ключи не получены. Интеграция должна показывать, что расходуется бесплатная ограниченная квота, ограничивать число вариантов и никогда молча не переключаться на платный workflow |
| API-format workflow | Пользователь сообщил пример ComfyUI `POST /prompt` графа с `AgnesImage` и `PreviewImage`; точный workflow и текущая схема `/object_info` ещё должны быть проверены перед реализацией |
| API `GET /prompts` = 404 | Само по себе не подтверждает отсутствие сохранённых workflows. Нужно экспортировать/проверить API-format workflow из интерфейса ComfyUI |
| `comfy_extras.nodes_ace` | В официальном ComfyUI v0.34.5 модуль содержит ACE-Step audio node IDs; это не опровергает пользовательскую проверку Agnes — модуль/источник фактических Agnes-классов нужно уточнить по живому `/object_info` и успешному workflow. [Источник](https://github.com/Comfy-Org/ComfyUI/blob/v0.34.5/comfy_extras/nodes_ace.py) |
| Git локального checkout | Локальный отчёт сообщает `HEAD=1fc2740` и расхождение с удалённой веткой от `cb3dcb9`; удалённая Arena-ветка на тот момент была `4014077`; локальный commit не найден в checkout Arena; автоматическая синхронизация не выполнялась |

Локальные модели, API-ключи, изображения и проектные данные не копировать в репозиторий. Наличие облачных custom nodes не означает, что ключи/кредиты настроены или что вызов безопасен без согласия.

## 2026-11-06 — ComfyUI discovery в фабрике, commit `b7256c4`

**Источник:** ручной отчёт пользователя о проверке в Windows; Arena не подключалась к компьютеру пользователя. Код проверялся на неизменённом commit `b7256c4`.

**Действия по отчёту:** запуск `python -m factory --port 7860`; `GET /api/settings`; вызов `POST /api/settings/comfyui/test` в API фабрики; проверены обращения фабрики к локальному ComfyUI. Состояние чистой проверки после этого восстановлено, согласно сообщению пользователя.

| Проверка | Результат |
|---|---|
| Настройка по умолчанию | `http://127.0.0.1:8188` |
| `GET /system_stats` | 200; CPU-only, 1 устройство, PyTorch `2.12.1+cpu` |
| `GET /object_info` | 200; получено 1053 node classes |
| Стандартные `CheckpointLoaderSimple`, `KSampler` | Найдены |
| `AgnesImage`, `AgnesText` | Найдены (`true` в UI/API фабрики) |
| API фабрики: settings и ComfyUI test | Оба запроса 200 |
| Workflow / `/prompt` | Не запускался / не вызывался |
| Версии окружения | ComfyUI backend `0.34.5`; Comfy Desktop `v1.1.8`; Python `3.13.12`; Windows `win32`; PyTorch `2.12.1+cpu` |

Это ручное LOCALLY-VERIFIED подтверждение только этапа безопасного discovery, не интеграции генерации изображений. Оно согласуется с unit-тестами `tests/test_comfyui.py`: пять тестов работают на mock-сервере и не заменяют реальную проверку. Никакой ключ или содержимое пользовательского workflow в репозиторий не добавлялись.

## 2026-11-06 — ComfyUI local txt2img profile, commit `4436091`

**Источник:** ручной отчёт пользователя о read-only/ dry-run проверке Windows; генерация не выполнялась.

| Проверка | Результат |
|---|---|
| Factory readiness | `python -m factory --port 7860`; `GET /api/settings` — 200 |
| Локальный профиль | `GET /api/settings/comfyui/local-profile` — 200; `comfyui-core-txt2img-v1`, `available=true` |
| Обнаруженные ресурсы | 3 checkpoint: `cyberrealistic_v80.safetensors`, `majicmixRealistic_v7.safetensors`, `realisticvisionmadne_v15.safetensors`; 42 sampler, 9 scheduler |
| Выбор модели | `cyberrealistic_v80.safetensors` сохранена через `PATCH /api/settings` и подтверждена `GET /api/settings` |
| Workflow builder (программный dry-run) | Создан API-format JSON-граф из 7 узлов; модель и параметры совпали с сообщёнными настройками: seed 42, steps 20, CFG 7.0, euler, normal, denoise 1.0, prefix `ai_video_factory` |
| POST `/prompt` / запуск workflow | Не выполнялся |
| После проверки | Factory остановлена, временные файлы удалены, Git рабочее дерево чистое (по отчёту пользователя) |

Это LOCALLY-VERIFIED подтверждение model discovery, сохранения выбора и программного экспорта графа на `4436091`; это не runtime-проверка генерации.

## 2026-11-06 — ComfyUI HTTP workflow export, commit `d8d970c`

**Источник:** ручной отчёт пользователя о проверке Windows; factory API ответил успешно, workflow в ComfyUI не запускался.

| Проверка | Результат |
|---|---|
| Factory readiness | `python -m factory --port 7860`; `GET /api/settings` — 200 |
| `POST /api/settings/comfyui/local-profile/workflow` | 200; вернулся `comfyui-core-txt2img-v1`, `submitted=false` |
| Сформированный граф | 7 узлов, модель `cyberrealistic_v80.safetensors`; seed 42, 512×512, 20 шагов, CFG 7.0, euler/normal, denoise 1.0; prefix `ai_video_factory` |
| ComfyUI API-вызовы из endpoint | Только GET `/object_info`; ComfyUI `/prompt` не вызывался |
| UI-клик/скачивание | Не проверялись этим отчётом; оставлены в следующем handoff |
| После проверки | Factory остановлена, временные файлы удалены, Git чистый (по отчёту пользователя) |

Это ручная проверка HTTP-export на `d8d970c`, не проверка сгенерированного изображения. Автотест подтверждает тот же endpoint на mock-сервере.

## 2026-11-06 — ComfyUI workflow export и граф на API, commit `d8d970c`

**Источник:** дополнительный отчёт пользователя о Windows-проверке. HEAD был detached `d8d970c`, рабочее дерево чистое; код соответствует потомку `335bb66`.

| Проверка | Результат |
|---|---|
| Factory readiness | `python -m factory --port 7860`; `GET /api/settings` — 200 |
| Model discovery | 3 checkpoint, 44 sampler, 9 scheduler; сохранён `cyberrealistic_v80.safetensors` |
| HTTP workflow export | `POST /api/settings/comfyui/local-profile/workflow` — 200; `profile_id=comfyui-core-txt2img-v1`; `submitted=false` |
| Состав графа | 7 узлов: CheckpointLoaderSimple, два CLIPTextEncode, EmptyLatentImage, KSampler, VAEDecode, SaveImage |
| Параметры тестового графа | 512×512; seed 12345; 25 steps; CFG 8.0; euler/normal; prefix `ai_video_factory` |
| ComfyUI `/prompt` | Не вызывался; проверено, что endpoint фабрики читает только GET `/object_info` |
| Browser UI click и скачивание JSON | Не проверялись буквально: отчёт был сделан API-запросом к тому же endpoint, который вызывает `exportLocalWorkflow()`; автоматизированный браузер недоступен |
| После проверки | Factory остановлена, временные файлы удалены, конфигурация `.factory` и Git-дерево чистые (по отчёту пользователя) |

Это подтверждает HTTP-export и 7-node payload, но не browser download и не локальную генерацию изображения.

## 2026-11-06 — A2 local image-job implementation (Arena mock only; NOT LOCALLY-VERIFIED)

**Статус:** новая реализация пока находится в незакоммиченном рабочем дереве Arena. Arena не подключалась к ComfyUI пользователя и не вызывала `/prompt`, Agnes или любой cloud API. Сетевые тесты используют только локальный fake HTTP server; пользователю не нужно передавать API key.

| Проверка | Результат |
|---|---|
| Explicit confirmation | UI сначала показывает план и browser confirm; image-run API отклоняет отсутствие явного согласия, разрешён только local / 0 EUR |
| Workflow | На `/object_info` строится стандартный 7-node graph; POST уходит только на валидированный loopback ComfyUI, Agnes nodes отсутствуют |
| Job/result | Mock проверяет POST `/prompt`, получение prompt_id, polling `/history`, скачивание `/view`, PNG и метаданные sampler/scheduler |
| Recovery/cancellation | Поддержано восстановление по сохранённому prompt_id; неизвестный исход POST fail-closed без повтора; queued job удаляется без глобального `/interrupt` |
| Asset/history | Валидированный PNG добавляется в immutable image history как `generated` / `comfyui_local_txt2img`, lifecycle `created`; автоматического выбора нет |
| Automated checks | 80 тестов, 1 optional skip (`imageio_ffmpeg` отсутствует); `node --check factory/web/app.js`, `node tests/test_action_ui.js`, `python -m py_compile factory/*.py`, `git diff --check` проходят |
| Local runtime/browser | Ещё не проверены в этой версии; handoff Windows test steps находятся в `ROADMAP.md` |

**Ожидаемый локальный отчёт:** версия Windows/Python/ComfyUI, выбранная локальная модель, шаги UI, длительность, появился ли unselected candidate и прошёл ли ручной select/render; явно отметить, что Agnes/cloud не запускался. Не включать ключи и личные данные, не удалять `.factory`/untracked-файлы и не делать push.

## Шаблон следующей проверки

```text
Дата:
Проверенный commit:
Локальная система: Windows / версия Python / версия ComfyUI (если применимо):
Задача и точные действия:
Профиль: локальный workflow / workflow с облачными нодами / Piper / другой локальный TTS
Модель/workflow (название и версия; без секретов):
Автоматические тесты и результаты:
Ручной результат: понятно / неразборчиво / артефакты / сцена подходит / не подходит
Длительность / ошибки:
Отправлялись ли данные внешнему сервису: нет / да (какие именно; расходы/лимит подтверждены):
Commit с кодом или отчётом, отправленный в общую ветку:
```
