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

console.log('F4/F5 UI render-state tests passed.');
