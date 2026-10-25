const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup() {
  const elements = new Map();
  const loads = [];
  const removed = new Set(['#download', '#toggle-public', '#toggle-code', '#code-panel', '#code', '#copy-code', '#new-video', '#failure-new']);
  function element(id) {
    assert.equal(removed.has(id), false, `Removed control still referenced: ${id}`);
    if (!elements.has(id)) {
      const node = { hidden: true, style: {}, dataset: {}, children: [], classList: { add() {} },
        addEventListener() {}, querySelectorAll: () => [], focus() {}, pause() {}, load() {},
        removeAttribute(name) { delete this[name]; },
        replaceChildren(...children) { this.children = children; },
        append() {}, appendChild() {}, setAttribute() {} };
      elements.set(id, node);
    }
    return elements.get(id);
  }
  const video = element('#video');
  let src;
  Object.defineProperty(video, 'src', { configurable: true, get: () => src,
    set: value => { src = value; loads.push(value); } });
  video.removeAttribute = name => { if (name === 'src') src = undefined; else delete video[name]; };
  const context = vm.createContext({
    $: element, Audio: class { addEventListener() {} pause() {} removeAttribute() {} },
    document: { createElement: () => element(`generated-${Math.random()}`) },
    enhancePlayer: () => ({ setTitle() {}, setChapters() {} }),
    ACTIVE: new Set(['queued', 'researching', 'writing', 'checking', 'rendering', 'reviewing']),
    STATUS_LABEL: {}, topTags: job => job.tags || [], formatDuration: n => String(n),
    clearInterval() {}, setInterval: () => 1, watch: () => () => {},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../create.js'), 'utf8'), context);
  const job = { id: 'one', topic: 'Bubble sort', title: 'Bubble sort', options: { review: true },
    progress: .8, created_at: 100, finished_at: 200, tags: [], ownedByMe: true,
    video_url: 'https://example.test/first-cut.mp4', thumbnail_url: 'https://example.test/thumb.jpg' };
  return { context, element, video, loads, job };
}

test('first-cut media stays hidden and unloaded throughout rendering and review', () => {
  const { context, element, video, loads, job } = setup();
  for (const status of ['queued', 'researching', 'writing', 'checking', 'rendering', 'reviewing', 'failed']) {
    context.renderJob({ ...job, status });
    assert.equal(element('#player').hidden, true, status);
    assert.equal(element('#job-ready').hidden, true, status);
    assert.equal(video.src, undefined, status);
  }
  assert.deepEqual(loads, []);
});

test('completion reveals only the final media and repeated live updates do not reload it', () => {
  const { context, element, video, loads, job } = setup();
  context.renderJob({ ...job, status: 'reviewing' });
  const final = { ...job, status: 'done', video_url: 'https://example.test/final.mp4' };
  context.renderJob(final);
  assert.equal(element('#job-ready').hidden, false);
  assert.equal(element('#player').hidden, false);
  assert.equal(element('#progress-wrap').hidden, true);
  assert.equal(video.src, final.video_url);
  context.renderJob(final);
  assert.deepEqual(loads, [final.video_url]);
});

test('moving back to an unfinished state or opening another job clears the previous result', () => {
  const { context, element, video, job } = setup();
  context.renderJob({ ...job, status: 'done' });
  context.renderJob({ ...job, status: 'reviewing' });
  assert.equal(video.src, undefined);
  assert.equal(element('#player').hidden, true);
  context.renderJob({ ...job, status: 'done' });
  context.showJob('another');
  assert.equal(element('#player').hidden, true);
  assert.equal(element('#job-ready').hidden, true);
  assert.equal(video.src, undefined);
});

test('a done record without a playable file does not announce a ready video', () => {
  const { context, element, loads, job } = setup();
  context.renderJob({ ...job, status: 'done', video_url: null });
  assert.equal(element('#player').hidden, true);
  assert.equal(element('#job-ready').hidden, true);
  assert.deepEqual(loads, []);
});
