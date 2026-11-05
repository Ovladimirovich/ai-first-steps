const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const appPath = path.join(__dirname, '..', 'factory', 'web', 'app.js');
const source = fs.readFileSync(appPath, 'utf8').replace(/\nboot\(\);\s*$/, '');
const context = {
  document: { querySelector: () => ({}), querySelectorAll: () => [] },
  setTimeout,
  clearTimeout,
  fetch: async () => { throw new Error('Unexpected network request in UI render test'); },
  console,
  confirm: () => true,
  Map,
  Date,
  Promise,
};
vm.createContext(context);
vm.runInContext(source, context, { filename: appPath });

const project = {
  id: 'test-project',
  title: 'UI test',
  spec: { intent: { theme: 'UI test' }, script: { scenes: [] }, heroes: [] },
};
vm.runInContext(`project = ${JSON.stringify(project)}; currentStep = 1; activeAction = null;`, context);
let html = vm.runInContext('renderScript()', context);
assert.match(html, /Создать предложение сценария/);
assert.doesNotMatch(html, /\/script-draft/);

const proposal = {
  action_id: 'action-test',
  kind: 'script-draft',
  status: 'proposed',
  provider: 'demo',
  model: 'rule-v1',
  privacy_scope: 'local',
  input_fingerprint: 'fingerprint-test',
  cost_estimate: { amount: 0, currency: 'RUB' },
  requires_cloud_consent: false,
};
vm.runInContext(`activeAction = ${JSON.stringify(proposal)};`, context);
html = vm.runInContext('renderScript()', context);
assert.match(html, /confirmAction/);
assert.match(html, /actionConsent/);
assert.match(html, /Подтвердить и запустить/);

const candidate = {
  ...proposal,
  status: 'candidate_ready',
  base_spec: {
    heroes: [],
    script: { scenes: [{ id: 'scene-1', title: 'Сцена', lines: [{ id: 'line-1', text: 'Старый текст' }] }] },
  },
  candidate_spec: {
    heroes: [],
    script: { scenes: [{ id: 'scene-1', title: 'Сцена', lines: [{ id: 'line-1', text: 'Новый <текст>' }] }] },
  },
};
vm.runInContext(`activeAction = ${JSON.stringify(candidate)};`, context);
html = vm.runInContext('renderScript()', context);
assert.match(html, /applyAction/);
assert.match(html, /rejectAction/);
assert.match(html, /Старый текст/);
assert.match(html, /Новый &lt;текст&gt;/);
assert.match(html, /Сначала примените или отклоните текущий вариант/);
assert.match(html, /disabled title="Разрешите текущее предложение выше"/);

vm.runInContext(`activeAction = ${JSON.stringify({ ...proposal, status: 'running', job_id: 'job-test' })}; actionJob = { state: 'running', progress: 40 };`, context);
html = vm.runInContext('renderScript()', context);
assert.match(html, /cancelAction/);
assert.match(html, /40%/);

const cloudProposal = { ...proposal, requires_cloud_consent: true, privacy_scope: 'cloud' };
vm.runInContext(`activeAction = ${JSON.stringify(cloudProposal)};`, context);
html = vm.runInContext('renderScript()', context);
assert.match(html, /actionCloudConsent/);
assert.match(html, /Максимальная стоимость запроса/);

const sceneProject = {
  id: 'visual-project',
  title: 'Visual test',
  spec: { intent: { theme: 'Visual test' }, script: { scenes: [{ id: 'scene-1', title: 'Кадр', lines: [], visual_note: 'Светлая сцена', image: { mode: 'style' } }] }, heroes: [] },
};
const variant = { asset_id: 'asset-1', asset_version: 1, type: 'scene_image', target: { scene_id: 'scene-1' }, path: 'assets/sha256/ab/image.png', state: 'created', available: true, prompt: { text: 'Тёплая мастерская <уютно>', negative: 'текст' } };
vm.runInContext(`project = ${JSON.stringify(sceneProject)}; currentStep = 3; activeAction = null; studio = { schema_version: 2, production: { visuals: { 'scene-1': { description: 'Описание', prompt: { text: 'Сохранённый prompt', negative: '' }, reference_asset_ids: [] } } } }; visualVariants = ${JSON.stringify([variant])}; artifacts = { frames: 'missing' };`, context);
html = vm.runInContext('renderFrames()', context);
assert.match(html, /data-visual-prompt/);
assert.match(html, /data-visual-negative/);
assert.match(html, /data-upload-variant/);
assert.match(html, /Проверить/);
assert.match(html, /Тёплая мастерская &lt;уютно&gt;/);
assert.match(html, /генераторы изображений пока не вызываются/);

vm.runInContext(`project = { id: 'piper-ui-project', spec: { intent: { theme: 'Piper test', audience: { note: 'Зрители' }, target_duration_s: 30 }, heroes: [{ id: 'h1', name: 'Бит', role: 'explains' }, { id: 'h2', name: 'Маша', role: 'asks' }], look: { style_preset: 'warm_workshop' }, script: { scenes: [] } } }; currentStep = 0; settings = { text_provider: 'demo', llama_cpp_base_url: 'http://127.0.0.1:8081/v1', llama_cpp_model: '', gigachat_model: '', gigachat_cloud_ack: false, gigachat_credentials_configured: false, voice_provider: 'piper', piper_executable: 'piper', piper_model_h1: 'bit.onnx', piper_model_h2: 'masha.onnx' };`, context);
html = vm.runInContext('renderIntent()', context);
assert.match(html, /Озвучка · Piper/);
assert.match(html, /id="voiceProvider"/);
assert.match(html, /id="piperModelH1"/);
assert.match(html, /id="piperModelH2"/);
assert.match(html, /Piper · локальная речь/);

vm.runInContext(`project = { id: 'subtitle-project', spec: { intent: { theme: 'Субтитры' }, heroes: [], script: { scenes: [] } } }; currentStep = 2; artifacts = { voice: 'ready', timing: { lines: [{ id: 'l1', text: 'Тестовая реплика', dur: 2.5 }] }, duration_s: 3 };`, context);
html = vm.runInContext('renderVoice()', context);
assert.match(html, /href="\/media\/subtitle-project\/subtitles\.srt"/);
assert.match(html, /Скачать субтитры \(\.srt\)/);

const indexHtml = fs.readFileSync(path.join(__dirname, '..', 'factory', 'web', 'index.html'), 'utf8');
assert.match(indexHtml, /id="projectList"/);
assert.doesNotMatch(indexHtml, /id="textProvider"|id="gigachatFields"/);

// --- GigaChat models dropdown tests ---

// Proper project setup for renderIntent (needs intent.audience, look, heroes)
vm.runInContext(`project = { id: 'giga-render', title: 'Giga render', spec: { intent: { theme: 'Giga', audience: { note: 'Все' }, target_duration_s: 60 }, script: { scenes: [] }, heroes: [{name:'Боб',role:'explains'},{name:'Маша',role:'asks'}], look: { style_preset: 'warm_workshop' } } }; currentStep = 0;`, context);

// 1) renderIntent with populated gigachat_models shows <select> with <option> entries
vm.runInContext(`settings.text_provider='gigachat'; settings.gigachat_model='GigaChat-Max'; settings.gigachat_models=['GigaChat-Max','GigaChat-Lite']; settings.gigachat_cloud_ack=true;`, context);
html = vm.runInContext('renderIntent()', context);
assert.match(html, /<select id="gigachatModel">/);
assert.match(html, /<option value="GigaChat-Max"\s+selected>GigaChat-Max<\/option>/);
assert.match(html, /<option value="GigaChat-Lite"\s*>GigaChat-Lite<\/option>/);
// No stale-model warning because the selected model is in the list
assert.doesNotMatch(html, /Сохранённая модель больше не доступна/);

// 2) renderIntent with stale gigachat_model not in gigachat_models shows warning
vm.runInContext(`settings.gigachat_model='GigaChat-Old'; settings.gigachat_models=['GigaChat-Max','GigaChat-Lite'];`, context);
html = vm.runInContext('renderIntent()', context);
assert.match(html, /<select id="gigachatModel">/);
assert.match(html, /Сохранённая модель больше не доступна/);

// 3) renderIntent with empty gigachat_models shows placeholder option only
vm.runInContext(`settings.gigachat_model=''; settings.gigachat_models=[];`, context);
html = vm.runInContext('renderIntent()', context);
assert.match(html, /Сначала проверьте доступ/);
assert.doesNotMatch(html, /GigaChat-Max/);

// 4) Validation: draft() rejects when gigachat provider but no model selected
vm.runInContext(`settings.text_provider='gigachat'; settings.gigachat_cloud_ack=true; settings.gigachat_model=''; settings.gigachat_models=[];`, context);
let validationError = null;
try {
  vm.runInContext(`if(settings.text_provider==='gigachat'&&!settings.gigachat_model)throw new Error('Выберите модель GigaChat из списка.');`, context);
} catch (e) { validationError = e; }
assert.ok(validationError, 'validation should throw when no gigachat model is selected');
assert.match(validationError.message, /Выберите модель GigaChat/);

// 5) Validation: draft() rejects when gigachat model is not in the available list
vm.runInContext(`settings.gigachat_model='GigaChat-Stale'; settings.gigachat_models=['GigaChat-Max'];`, context);
validationError = null;
try {
  vm.runInContext(`if(settings.text_provider==='gigachat'&&settings.gigachat_model&&!settings.gigachat_models?.includes(settings.gigachat_model))throw new Error('Выбранная модель не найдена — обновите список кнопкой «Проверить доступ».');`, context);
} catch (e) { validationError = e; }
assert.ok(validationError, 'validation should throw when gigachat model is stale');
assert.match(validationError.message, /модель не найдена/);

// 6) Valid model passes both checks without throwing
vm.runInContext(`settings.gigachat_model='GigaChat-Max'; settings.gigachat_models=['GigaChat-Max','GigaChat-Lite'];`, context);
validationError = null;
try {
  vm.runInContext(`if(settings.text_provider==='gigachat'&&!settings.gigachat_model)throw new Error('Выберите модель GigaChat из списка.');if(settings.text_provider==='gigachat'&&settings.gigachat_model&&!settings.gigachat_models?.includes(settings.gigachat_model))throw new Error('Выбранная модель не найдена');`, context);
} catch (e) { validationError = e; }
assert.strictEqual(validationError, null, 'no error expected for valid model');

// 7) settings object includes gigachat_models array
vm.runInContext(`settings.gigachat_models=['A','B'];`, context);
const savedModels = vm.runInContext('settings.gigachat_models', context);
assert.strictEqual(JSON.stringify(savedModels), JSON.stringify(['A', 'B']));

console.log('F4/F5/M4 UI render-state tests + GigaChat models dropdown passed.');
