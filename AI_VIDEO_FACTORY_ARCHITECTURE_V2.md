# AI Video Factory — архитектура студии v2

**Статус:** архитектура утверждена пользователем; backend F1 и ядро F2 реализованы в рабочей Arena-ветке. F2 включает вычисляемые fingerprints и immutable asset storage; F3, UI-подключение draft и реальные AI media providers не входят в этот этап. Существующие v1 проекты не мигрируются автоматически.

**Результат F1:** новые проекты сохраняются как `spec_version: 2` и отдельный `production.json`; старый UI/renderer продолжает получать v1-совместимую проекцию. Добавлены revision snapshots, раздельные `spec_revision`/`production_revision`, restore как новая ревизия, атомарная запись JSON и явный read-only migration plan / confirm-bound apply для v1. Persisted working-draft API реализован без подключения UI.

**Результат F2:** добавлены canonical dependency fingerprints по каждой реплике, сцене, таймингу, кадру/сегменту и отдельно Preview/Final Render; входы учитывают model/version, prompt, параметры и content hashes, секреты и volatile UI/action metadata исключаются. Новый v2 upload и результаты pipeline пишутся как content-addressed asset versions, manifest append-only, а легаси-пути остаются совместимыми alias. Реализован read-only `GET /api/projects/{id}/fingerprints` с детальными статусами и stale reasons. F2 не запускает генерацию, не меняет legacy renderer и не мигрирует v1.

## 1. Цель и инварианты

Студия расширяет существующую фабрику, сохраняя её текущую главную цепочку:

`тема → сценарий → реплики → озвучка → тайминг → изображения → видео`

Обязательные инварианты:

1. **Сценарий — единственный первичный источник повествовательного содержания.** Озвучка, изображения, тайминг и видео — зависимые производные артефакты. Они не могут незаметно менять тему, сцены или реплики.
2. **ИИ создаёт предложения и варианты.** Каноническая спецификация меняется только после явного принятия пользователем. Отклонённый или неподтверждённый результат не становится выбранным ассетом.
3. **История неразрушающая.** Принятые ревизии и медиафайлы не перезаписываются; восстановление создаёт новую ревизию на основе выбранного снимка.
4. **Ревизии разделены по смыслу.** Содержание, производственные указания, медиа и сборки версионируются независимо.
5. **Устаревание вычисляется по точным зависимостям и fingerprints**, а не определяется сравнением только общей ревизии проекта.
6. **Preview и Final Render — разные типы артефактов, профилей и задач.** Preview не запускает и не заменяет финальный рендер.
7. **Затратная или внешняя операция сначала получает оценку и подтверждение.** Подтверждение относится к конкретным данным, провайдеру, настройкам и цене; после их изменения оно недействительно.
8. **Один профиль локальной модели одновременно.** Ресурсоёмкие вызовы локального GPU проходят через последовательную очередь; секреты провайдеров не входят в спецификацию, журнал, ответы API или браузер.
9. **Существующий легаси-рендерер и старые проекты сохраняют работоспособность.** Новая модель адаптируется к рендереру через явный экспортный адаптер.

## 2. F0 — аудит текущего состояния

Аудит выполнен по текущему дереву `factory/`, тестам, документации и проектным файлам в `.factory/`. Неотслеживаемые и игнорируемые пользовательские данные в документ не копируются.

### 2.1. Текущая схема и сохранение

- `factory/core.py`: `new_spec()` создаёт `spec_version: 1` с `intent`, `heroes`, `look`, `format`, `timing_policy` и `script.scenes[].lines[]`.
- Сцены и реплики уже имеют стабильные строковые `id`; это можно сохранить в v2. У сцены есть `title`, `purpose`, `goal`, `visual_note`, `image`; у реплики — `hero`, `text`, `pause_after_s`.
- Каждый проект хранится в `.factory/projects/<project_id>/`: `project.json` содержит метаданные и текущий `revision`, `spec.json` — спецификацию. `save_project()` записывает эти два файла отдельно; атомарной транзакции для пары сейчас нет.
- `PATCH /api/projects/{id}` проверяет `revision`, увеличивает его и возвращает `409` при устаревшей версии. Автосохранение редактора сейчас превращает рабочие правки в принятую ревизию; отдельного сохраняемого черновика редактора и истории принятых версий нет.
- `validate_spec()` валидирует v1, но миграционного слоя v1→v2 пока нет.

### 2.2. Артефакты и кэш

- `artifact_state()` в `factory/core.py` вычисляет общие fingerprints голоса, кадров и рендера. Результат имеет состояние `missing / ready / stale`.
- `factory/pipeline.py` хранит `voice-cache.json`, `frames-cache.json` и `segment-cache.json`; для озвучки/кадров/рендера используются метафайлы и кэши. Кэш сегментов уже позволяет пересобрать затронутые сцены.
- Загруженные фоны сохраняются в каталоге проекта; выбранный путь привязан к сцене через `image.mode/path`. Изображения и результаты генерации пока не имеют общего неизменяемого реестра вариантов.
- Текущие артефакты: `audio/`, `frames/`, `segments/`, `renders/draft.mp4`, `renders/final.mp4`, `timing.json`, `subtitles.srt`, scene-backgrounds и соответствующие `*.meta.json`/`*-cache.json`.
- Текущий `draft` и `final` — разные качества сборки в одном производственном конвейере, а не полностью независимые процессы с отдельными профилями и жизненными циклами.

### 2.3. Провайдеры и задания

- `factory/providers.py`: текстовые провайдеры demo, llama.cpp и GigaChat; генерация llama.cpp сериализована. Секреты GigaChat читаются серверной частью из `.env`/окружения.
- Настоящие TTS, генерация изображений и музыки не подключены. Текущая озвучка — явно обозначенная тишина; изображения формируются рендерером или загружаются пользователем.
- `factory/pipeline.py`: `PLANS` и `JOBS` существуют в памяти процесса. План привязан к `project_id`, `revision`, `spec_hash`, stage и kind; устаревший план отклоняется. `_worker_lock` сериализует производственные задачи в текущем процессе.
- Текущие состояния задачи: `queued`, `running`, `done`, `error`. Устойчивого журнала задач, отмены, повтора и возобновления после перезапуска нет.

### 2.4. Точки входа, которые будут затронуты после утверждения

| Область | Текущие файлы | Назначение в будущей архитектуре |
|---|---|---|
| Модель и валидация | `factory/core.py` | Совместимый фасад для v1/v2; не место для всей логики хранения/очереди |
| HTTP API | `factory/server.py` | Существующие маршруты оставить адаптером; добавить версионированные studio/revision/action/job маршруты |
| Pipeline | `factory/pipeline.py` | Использовать выбранные asset IDs и профиль, создавать preview/final как разные артефакты |
| Провайдеры | `factory/providers.py`, `factory/settings.py` | Расширять интерфейсами моделей/оценок; секреты остаются серверными |
| UI | `factory/web/app.js`, `index.html`, `style.css` | Единая студия с редакторами, diff/вариантами, stale-бейджами и очередью |
| Рендерер | `tools/build_ffmpeg_video.py` | Сохранить legacy default; вызывать через адаптер фабрики |
| Тесты | `tests/test_factory.py` | Разделить по миграции, ревизиям, fingerprints, ассетам, действиям, очереди и API |

## 3. Предлагаемое разделение данных

### 3.1. `spec.json` — содержание ролика

`spec_version: 2` описывает повествовательный канон, а не железо или настройки кодека:

- тема, аудитория, язык, образовательная цель;
- герои: устойчивый `hero_id`, имя, роль и повествовательная характеристика;
- сцены с устойчивым `scene_id`, порядком, заголовком, задачей сцены;
- реплики с устойчивым `line_id`, `hero_id`, точным текстом и редакционными паузами;
- происхождение принятого содержания: кто/какое действие его предложило и кто применил — через ссылку на revision/action, не секреты провайдера.

Смысловые изменения — тема, структура сцен, заголовок/цель как часть содержания, текст и порядок реплик — увеличивают `spec_revision`.

### 3.2. `production.json` — производственное направление

Отдельная версионируемая модель по стабильным ID из сценария:

- `visuals[scene_id]`: визуальное описание, prompt/negative prompt, reference asset IDs, выбранный image asset ID;
- `dialogue[line_id]`: голос героя или переопределение для реплики, интонация, темп, ударения, произношение, выбранный audio asset ID;
- музыкальный brief и cue map, привязанный к `scene_id`/`line_id` и offset, а не только к абсолютным секундам;
- активные профили Preview и Final Render;
- ссылки на производственные провайдеры/модели и параметры по умолчанию без секретов.

Изменение prompt, интонации, музыки или технического профиля увеличивает `production_revision`, но не меняет `spec_revision`. Текущие `look`, `format`, `timing_policy` и `heroes[].voice` при миграции распределяются между содержанием и производственным направлением по таблице в §7.

### 3.3. Ревизии и рабочие черновики

Предлагается хранить четыре независимых измерения:

- `project_revision` — optimistic concurrency token для API и вкладок; увеличивается при любом зафиксированном изменении.
- `spec_revision` — монотонный номер принятой версии содержания.
- `production_revision` — монотонный номер принятой версии производственных указаний/профилей.
- `asset_version` и `render_version` — последовательность неизменяемых медиа-версий и сборок в пределах соответствующего объекта/проекта.

Принятая версия сохраняется как неизменяемый полный снимок `spec` и `production` под `revisions/<revision_id>/`. Полный снимок малых JSON-документов предпочтительнее сложного diff для восстановления. Дифф можно сохранять дополнительно для UI.

Редактор ведёт рабочую копию отдельно, например `drafts/<session_id>.json`, с `base_project_revision`, `base_spec_revision` и `base_production_revision`. Автосохранение рабочей копии не меняет канонический снимок. Кнопка «Применить/Сохранить» создаёт новую принятую ревизию. Если базовая ревизия устарела, API возвращает `409`; UI предлагает обновить/сравнить, а не затирает чужие правки.

Восстановление ревизии R не передвигает указатель назад и не удаляет новые версии. Оно создаёт новую ревизию R+1, содержимое которой скопировано из R; связанные ассеты остаются доступны.

### 3.4. Производственные профили

Профиль хранится отдельно от `spec.json`, имеет свой ID, revision и fingerprint.

```json
{
  "profile_id": "preview-720p-v1",
  "kind": "preview",
  "width": 1280,
  "height": 720,
  "fps": 30,
  "video": {"container": "mp4", "codec": "h264", "quality": "draft"},
  "audio": {"codec": "aac", "sample_rate": 44100, "channels": 2},
  "renderer": {"name": "legacy-ffmpeg", "version": "..."},
  "limits": {"max_duration_s": 120, "max_scenes": null}
}
```

Preview и Final Render имеют разные profile IDs. Смена codec/CRF/preset/разрешения инвалидирует лишь зависимые сборки, не сценарий и не исходные медиа. Версии renderer/encoder включаются в render fingerprint. Настройки оборудования/пути к исполняемым файлам и учётные данные остаются в локальных настройках, не в проекте.

## 4. Реестр ассетов и жизненный цикл

`studio/assets.json` — каталог неизменяемых файлов. Предлагаемые поля записи:

```json
{
  "asset_id": "as_<uuid>",
  "type": "scene_image",
  "target": {"scene_id": "s1"},
  "sequence": 2,
  "path": "studio/media/images/as_<uuid>.png",
  "sha256": "...",
  "mime": "image/png",
  "size_bytes": 12345,
  "source": "generated",
  "provider": "...",
  "model": {"id": "...", "version": "..."},
  "prompt": {"text": "...", "negative": "..."},
  "parameters": {},
  "input_fingerprint": "...",
  "created_at": "...",
  "created_by": "user",
  "action_id": "act_..."
}
```

- Asset file и provenance после создания не меняются. Исправленный файл — новая запись/версия.
- Текущий выбранный вариант указывается ссылкой в `production.json`; принятие — событие журнала. Не нужно мутировать все старые записи из `candidate` в `selected`.
- Жизненный цикл: `created → reviewed → selected` либо `rejected`; это события. Состояния `stale`, `missing`, `orphaned` вычисляются из fingerprint/наличия файла/ссылок.
- Upload — такой же asset с `source: uploaded`, sha256, проверенным MIME и локальным путём. Старое поле v1 `image.path` переносится в manifest без перемещения/удаления исходника до успешной миграции.
- Кэш — удаляемое промежуточное вычисление; ассет — пользовательский результат. Кэш нельзя считать единственной копией выбранного варианта.
- Повторная генерация не заменяет asset и не удаляет старые варианты. Очистка orphaned-файлов — отдельная операция с предварительным списком и подтверждением; по умолчанию не удалять.

## 5. Fingerprints и граф зависимостей

### 5.1. Общие правила

Fingerprint — SHA-256 от канонического JSON: UTF-8, сортировка ключей, нормализованные числа/строки, без timestamp, случайного `action_id` и полей UI. Каждый тип fingerprint получает namespace и версию алгоритма, например `voice-input:v1`. Выходной файл имеет отдельный `content_sha256`.

Включать все параметры, способные изменить результат: target IDs, точные входные тексты/ссылки, prompt и references по content hash, provider/model и доступную версию, voice identity, delivery параметры, seed, generation parameters, выбранный profile, renderer и encoder версии. Секреты, токены и локальные пути к секретам никогда не входят в fingerprint.

Если API не раскрывает точную версию развёрнутой модели, фиксировать provider-reported model ID и `version_confidence: unknown`; не обещать точную воспроизводимость.

### 5.2. Зависимости по типам

| Выход | Входы fingerprint | Что не должно его менять |
|---|---|---|
| Текст реплики/сцены | Принятые намерение/аудитория, целевой текстовый контекст, provider/model/version, prompt template/version и параметры действия | Кодек, FPS, параметры рендера |
| Диалоговый audio asset | Точный текст реплики, язык, voice ID/provider/model/version, emotion/pace/emphasis/pronunciation, generation parameters, версия TTS | Визуальный prompt, image renderer |
| Изображение сцены | Смысловые поля этой сцены и относящиеся к ней реплики, prompt, style, reference asset hashes, image provider/model/version, seed и параметры | Настройки аудиокодека, громкость музыки |
| Музыка/cue | Music brief, cue anchors, связанный сценарный контекст и тайминг, provider/model/version, музыкальные параметры | Разрешение видео |
| Timing | Тексты/ID реплик, паузы, правила темпа/языка и версия timing engine | Кодек, профиль изображения |
| Preview | Выбранные версии зависимых assets, сценарий/timing, preview profile, renderer version | Final profile; final не становится preview |
| Final Render | Выбранные изображения, диалог и музыка; subtitles/timing; production profile; renderer/encoder версии | Не связанные с проектом assets и неиспользованные кандидаты |

Для зависимых источников хранить fingerprints по сущностям, а не один общий hash всего проекта. Тогда правка строки инвалидирует только её звук, связанные тайминги, affected previews/renders и визуальные варианты, где эта строка участвует в prompt-контексте.

Техническое изменение только `codec`/`CRF` меняет fingerprint соответствующего Render, но не `spec_revision`, image/audio fingerprints или выбранные source assets. Смена FPS инвалидирует сборку и только те производные тайминги, для которых FPS действительно является входом.

**Реализация F2 v1:** `factory/fingerprints.py` использует canonical SHA-256 serialization и dependency vectors; `factory/assets.py` хранит v2 uploads/derived outputs в `assets/sha256/` и добавляет их в append-only manifest. `GET /api/projects/{id}/fingerprints` выполняет принудительную проверку hash выбранных/используемых файлов; обычный status API использует stat-aware hash cache, чтобы не читать большие renders при каждом опросе. Stale состояния и `changed_dependencies` считаются раздельно для line voice, scene image inputs, frame, scene segment, Preview и Final. Старые unverified ассеты сохраняются; повреждение/отсутствие выявляется при проверке используемой версии.

## 6. Предложения ИИ, подтверждение и проверяемая история

### 6.1. Модель действия

Каждый AI action хранит как минимум:

- `action_id`, тип операции и target IDs;
- actor (`user`, `ai`, `system`) и session ID;
- базовые `project/spec/production` revisions и точный `input_fingerprint`;
- provider, model/version, prompt/template version и параметры; секреты исключены;
- proposal/diff или ссылки на candidate assets;
- оценку `min/max`, currency, единицы, источник тарифа, время и срок действия quote;
- cloud/privacy consent scope и user confirmation ID;
- job ID, outputs, errors и итоговое решение пользователя.

### 6.2. Состояния и применение

Для текстового/бесплатного предложения:

`proposed → accepted → applied` либо `proposed → rejected`.

Для генерации/платной операции:

`proposed → awaiting_approval → queued → running → completed(candidate) → accepted(selected)`.

Альтернативные конечные состояния: `rejected`, `failed`, `cancelled`, `stale`. Получение candidate output не означает его применение.

- Пользователь до подтверждения видит diff, target, провайдера, входные данные, оценку затрат/времени и privacy notice.
- Confirmation привязано к `action_fingerprint`, стоимости/верхней границе и consent scope. Изменение параметра или истечение quote требует нового подтверждения.
- Если точную цену нельзя получить, UI показывает `unknown`; перед отправкой пользователь задаёт допустимый лимит/подтверждает неопределённость. Платный вызов без этого не запускается.
- Применение текстового diff создаёт новую spec/production revision с указанием `action_id`. Выбор медиа-кандидата обновляет выбранный asset pointer в новой production revision.
- `actions.jsonl` — append-only журнал событий с `prev_event_hash` и `event_hash` для обнаружения незаметного изменения истории. Это tamper-evident журнал, не цифровая подпись и не защита от владельца файловой системы, переписывающего все копии. Не писать туда API secrets/tokens.
- Событие включает использованный вход или ссылку на неизменяемый revision/asset snapshot, proposal, решение пользователя и итог. Для локального пользователя actor — локальный user ID; секреты не попадают в UI и лог.

## 7. Миграция v1 → v2 без потери старых проектов

Миграция должна быть повторяемой, проверяемой и атомарно активируемой. Никакой автоматической перегенерации или удаления старых файлов.

| v1 поле/артефакт | v2 назначение | Правило |
|---|---|---|
| `spec.intent`, `script.scenes[].lines[]` | `spec.json` v2 | Сохранить содержимое, IDs, порядок и тексты без переформулирования |
| `heroes[].id/name/role/about` | v2 heroes | Сохранить IDs; не выводить новую личность автоматически |
| `heroes[].voice` | `production.json.dialogue` defaults для героя | Перенести voice provider/ID/rate; без вызова TTS |
| `look`, scene `visual_note` | `production.json.visuals` | Перенести style/palette и описание; prompt не генерировать автоматически |
| `scene.image.mode=upload/path` | asset manifest + выбранный asset pointer | Проверить путь внутри проекта, MIME/hash; сохранить файл, не перемещая до commit миграции |
| `format`, `timing_policy` | Preview/Final profiles + timing policy | Сохранить размер, FPS, captions и правила; не запускать рендер |
| `voice.meta.json`, `frames.meta.json`, `render.meta.json` | legacy asset/production records | Перенести известные hashes и пути; неизвестное происхождение пометить `legacy_unverified`, не объявлять автоматически свежим/устаревшим |
| `project.json.revision` | `project_revision`/baseline | Сохранить исходное значение для API совместимости; установить baseline spec/production snapshots |
| существующие cache-файлы | legacy cache namespace | Не удалять; кэш с несоответствующим v2 fingerprint перестаёт быть reusable, но остаётся до очистки |

Порядок:

1. Dry-run: распознать v1, проверить все ссылки/пути/ID, составить план и отчёт о проблемах.
2. Создать неизменяемую резервную копию v1 JSON и необходимые хэши; не включать `.env`.
3. Сформировать v2 `spec`, `production`, revision baseline и asset manifest во временном каталоге проекта.
4. Валидировать всё, проверить доступность и sha256 каждого связанного файла и возможность открыть старые видео/ассеты.
5. Только после успешной проверки атомарно установить migration marker/current schema pointer. При любой ошибке оставить v1 активной и показать отчёт; partial v2 удалить можно только из staging-каталога миграции.
6. После миграции читать старые маршруты через v1-compatible facade. Обратная миграция не обязательна: оригинальный v1 backup остаётся доступным.

Миграция не должна утверждать, что старые файлы воспроизводимы до бит-в-бит: если старой модели/renderer version нет, фиксировать это как ограничение provenance.

## 8. Производственная очередь

### 8.1. Job record и состояния

Устойчивая запись job содержит `job_id`, `project_id`, action/stage, resource class, priority/FIFO sequence, исходный fingerprint, подтверждение/quote ID, checkpoints, progress, попытки, timestamps и error summary.

Стандартизированные состояния:

- `queued`
- `running`
- `completed`
- `failed`
- `cancelled`

Состояние `completed` означает завершение вычисления, но не принятие candidate ассета пользователем.

### 8.2. Правила исполнения

- Одна очередь на приложение; для локального GPU semaphore/capacity = 1. Нельзя одновременно загрузить два профиля локальной модели.
- В v1 очереди поддержать одну активную производственную задачу и сохранять очередь на диск; приоритет preview допустим, но без голодания уже ожидающих задач.
- Сохранять checkpoint после каждой реплики/сцены/сегмента. Завершённые части повторно используются только при совпадении их fingerprints.
- `cancel` для `queued` выполняется сразу; для `running` — кооперативно между единицами работы. Если внешний API нельзя прервать, результат позднего ответа сохраняется как candidate либо отбрасывается согласно отмене, но не применяется автоматически.
- `retry` разрешён для `failed`/`cancelled` только при том же fingerprint и действующем подтверждении. При изменённых входных данных создаётся новое действие/смета.
- После перезапуска приложения `queued` восстанавливаются; `running` без валидного worker lease переводятся в `failed/interrupted` с предложением Resume/Retry. Не объявлять успешными незаписанные outputs.
- Файлы сначала записываются во временное имя, проверяются, затем публикуются через atomic replace. Источник/выбранный asset не затирается.

### 8.3. Переход от текущего состояния

Текущие `JOBS`/`PLANS` и `_worker_lock` в памяти не обеспечивают перезапуск, cancel и retry. На F3 заменить volatile очередь на персистентные job records и lock; сохранить одну локальную GPU задачу. При чтении старых статусов отображать `done → completed`, `error → failed`; dangling `running` после рестарта считать interrupted.

## 9. Предлагаемый API

Новые маршруты пока проектируются; точные URL можно стандартизировать на F1. Предлагаемый контракт:

| Метод/путь | Роль |
|---|---|
| `GET /api/v2/projects/{id}/studio` | Нормализованные spec/production, revision tokens, текущие stale/fresh статусы |
| `PATCH /api/v2/projects/{id}/drafts/{session_id}` | Сохранить временный рабочий черновик, не коммитить канон |
| `POST /api/v2/projects/{id}/revisions` | Принять выбранные изменения; `expected_*_revision` обязателен |
| `GET /api/v2/projects/{id}/revisions` / `GET .../{revision_id}` | История и конкретный неизменяемый снимок |
| `POST /api/v2/projects/{id}/revisions/{revision_id}/restore` | Создать новую revision из старого snapshot; не откатывать счётчик |
| `GET /api/v2/projects/{id}/assets` / `GET .../assets/{asset_id}` | Manifest и неизменяемые варианты |
| `POST /api/v2/projects/{id}/ai/actions` | Создать предложение, diff и/или quote; не выполнять дорогой вызов без approval |
| `GET /api/v2/projects/{id}/ai/actions/{action_id}` | Статус предложения, cost estimate, provenance и outputs |
| `POST .../ai/actions/{action_id}/confirm` | Проверить fingerprint/quote/consent и поставить выполнение в очередь |
| `POST .../ai/actions/{action_id}/apply` / `reject` | Принять предложение/выбрать asset или отклонить; принятие создаёт новую revision/event |
| `GET /api/v2/jobs/{job_id}` / `POST .../cancel` / `POST .../retry` | Наблюдать/управлять производственной задачей |
| `POST /api/v2/projects/{id}/preview-plans` и `POST .../previews` | Отдельная оценка и запуск быстрого превью |
| `POST /api/v2/projects/{id}/render-plans` и `POST .../renders` | Отдельные смета и запуск Final Render |

Все изменяющие запросы принимают ожидаемые revisions или ETag. Устаревший запрос возвращает `409` с текущими revision tokens и не применяет частичные изменения. Старые `/api/projects/...` маршруты остаются фасадом до полного перехода UI и клиентов; они не должны обходить revision/approval правила.

## 10. Тестовая стратегия и критерии приёмки F0–F3

### F0 — аудит

- Зафиксировать текущие routes, schema, generated files, cache namespaces, renderer CLI, `.gitignore`/секреты и legacy smoke commands.
- Снять хэши sample v1 проекта и его выбранных файлов; в отчёт не копировать содержимое приватных проектов/секреты.
- Результат: baseline/fixture, список фактов и несовместимостей.

### F1 — схема, snapshots, адаптер и миграция

- Fixture v1 мигрирует в v2 с теми же scene/line IDs и побайтно теми же текстами.
- Dry-run не меняет файлы; ошибка в ссылке/JSON оставляет v1 активной.
- Повтор миграции идемпотентен; backup и старый MP4 остаются доступными.
- Принятое изменение создаёт новую spec/production revision; restore создаёт новую ревизию и сохраняет промежуточные версии.
- Устаревшая вкладка получает 409, не затирает новый snapshot.

### F2 — ассеты/fingerprints/зависимости

- Одинаковые канонические входы дают одинаковый fingerprint; изменение каждого значимого параметра — другой hash.
- Не меняют fingerprint нерелевантные timestamp/UI поля.
- Отдельная матрица mutation→stale для текста, prompt, reference image, voice/model/delivery, cue, timing, codec/FPS/renderer.
- Новый вариант не перезаписывает файл/запись; выбор варианта создаёт production revision.
- Legacy assets с неполным provenance обозначаются `legacy_unverified`; никаких неявных regeneration.
- F2 реализовано: canonical fingerprints и dependency vectors проверены mutation-тестами; загрузки и новые pipeline outputs v2 используют content-addressed неизменяемые версии, append-only asset manifest и совместимые старые пути.
- Автоматического real render/image/TTS вызова нет. Интеграционная проверка реального MP4 на локальном Pillow/MoviePy окружении требуется локальному инженеру; renderer-команда не менялась.

### F3 — action log, gates, очередь

- Журнал append-only: hash-chain верифицируется, повреждение обнаруживается; секреты не появляются в событиях/ошибках/API.
- AI proposal не меняет spec/production до `apply`; действие с изменившимся fingerprint и старая смета отклоняются.
- Без confirmation и действующей cost ceiling платная задача не отправляется провайдеру.
- Проверить все переходы `queued/running/completed/failed/cancelled`, cancel в ожидании и на границе checkpoint, retry/resume после перезапуска, idempotent outputs.
- Одновременно запущено не больше одного local GPU worker/profile; мок-провайдеры используются в unit-тестах.
- При crash процесс не теряет завершённые checkpoints и не маркирует неполный output готовым.

### Сквозные проверки

- Старые тесты и прежняя команда легаси-рендера проходят без изменения поведения по умолчанию.
- Тесты API/UI: две вкладки с конфликтом, принятие/откат snapshot, stale badge, diff/apply/reject, cancel/retry, загрузка файла с проверкой пути и MIME.
- Preview никогда не записывается как Final Render; изменение production profile не меняет story revision.
- Демо-сценарий/тишина явно маркируются; тесты не требуют реальных GigaChat/TTS/image/music секретов и сетевых платных вызовов.

## 11. Предварительный список будущих файлов

Точный список уточняется после утверждения F1. Предлагаемая ответственность:

| Файл | Будущая ответственность |
|---|---|
| `factory/schema_v2.py` | Типы/дефолты/валидаторы v2 и нормализованное чтение v1 |
| `factory/migrations.py` | Dry-run, v1→v2 staging, backup, integrity checks и activation marker |
| `factory/revisions.py` | Принятие изменений, snapshots, compare/restore и optimistic concurrency |
| `factory/fingerprints.py` | Canonical serialization, namespaces и entity dependency hashes |
| `factory/assets.py` | Manifest, import/immutability, provenance, selection references и orphan audit |
| `factory/actions.py` | AI proposals, consent/quote binding, apply/reject и event log |
| `factory/jobs.py` | Персистентная очередь, checkpoints, recovery/cancel/retry, GPU capacity=1 |
| `factory/storage.py` | Atomic file writes, project locks, path containment, backup/transaction helpers |
| `factory/server.py` | Новые API v2 плюс backward-compatible v1 facade |
| `factory/pipeline.py` | Asset/profile-aware preview/final pipeline без изменения legacy default |
| `factory/web/studio.js` или `factory/web/app.js` | UI редакторов, draft vs accepted state, diff, timeline/history, job queue |
| `tests/test_migrations.py`, `test_revisions.py`, `test_fingerprints.py`, `test_assets.py`, `test_actions.py`, `test_jobs.py`, `test_api_v2.py` | Раздельные тесты каждого контракта |

Новые библиотеки не предполагаются на этапе проектирования; базовое хранение можно оставить на JSON/JSONL и стандартной библиотеке, если F0 подтвердит достаточность файловых блокировок и атомарной записи для одного локального процесса. Если обнаружатся требования нескольких процессов/пользователей, до F1 отдельно сравнить файловую схему с SQLite.

## 12. Предлагаемая последовательность реализации после утверждения

1. **F0 (аудит, сейчас):** этот документ и согласование фактов/контрактов; без изменений production-кода.
2. **F1:** v2 модели, v1 read-adapter, staging migration, immutable revision snapshots/restore.
3. **F2:** ✅ backend реализован — append-only manifest, immutable content-addressed variants, dependency fingerprints и stale reasons; ожидается локальный smoke-test реального renderer pipeline.
4. **F3:** append-only action journal, cost/consent gates, персистентная очередь и recovery.
5. **F4:** редактор сценария с рабочим draft, diff/accept/reject и быстрым preview.
6. **F5:** prompts и история визуальных вариантов; реальные провайдеры только после отдельного выбора/оценки.
7. **F6:** диалоговый TTS и музыка; демо-тишина остаётся честно помеченной до реального подключения.
8. **F7:** независимые Preview/Final профили и процессы.
9. **F8:** автоматизация только из проверяемых пользовательских правил; никогда не обходить consent, cost gate или принятие результата.

## 13. Принятые контракты и граница F1/F2

Следующие контракты закреплены пользовательским решением и положены в основу F1:

1. Разделение файлов на `spec.json` (история/текст), `production.json` (визуальное/голосовое/музыкальное направление и активные профили), `assets.json` (неизменяемый manifest), snapshots в `revisions/`, журнал `actions.jsonl`, черновики в `drafts/`.
2. Снимок принятой revision хранит полные JSON `spec` + `production`; restore всегда создаёт новую revision.
3. `production_revision` увеличивается на любое принятое производственное изменение, но stale вычисляется по тонким fingerprints, чтобы изменение кодека не инвалидировало изображения/аудио.
4. Существующие ассеты с неполными метаданными получают `legacy_unverified` и сохраняются; автоматическая миграция не запускает генерацию.
5. Журнал `actions.jsonl` использует hash-chain для обнаружения изменений; он не является криптографически подписанным аудитом.
6. Персистентная очередь в первом локальном релизе — файловая с atomic replace и одним серверным процессом; SQLite рассматривается только если F0 выявит недостаточность файловой транзакционности.

**Граница поставки:** F1 и F2 backend реализованы и проходят sandbox/unit/API тесты. Существующие v1 проекты остаются нетронутыми до явного вызова migration/apply с актуальным fingerprint. Реальный локальный MP4 pipeline следует проверить после переноса F2 в рабочую `main`; в этом sandbox отсутствует Pillow, поэтому end-to-end render не запускался. F3 (append-only action journal и персистентная очередь), UI-подключение draft/accept и реальные image/TTS/music providers не реализованы.
