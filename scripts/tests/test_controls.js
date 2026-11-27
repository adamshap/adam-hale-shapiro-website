const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../../docs/assets/site.js'), 'utf8');

function environment(selectors = {}) {
  const document = {
    documentElement: { classList: { add() {} } },
    querySelector: (selector) => selectors[selector]?.[0] || null,
    querySelectorAll: (selector) => selectors[selector] || [],
    execCommand: () => false,
  };
  const timers = [];
  const context = { document, navigator: {}, Intl, innerWidth: 390,
    window: { addEventListener() {} },
    setTimeout: (fn) => { timers.push(fn); return timers.length; }, clearTimeout() {} };
  return { context, document, timers };
}

function copyButton() {
  const events = {};
  const attrs = { 'aria-label': 'Copy BibTeX for Example paper' };
  const citation = { value: '@article{example,\n  title = {{Example paper}},\n}\n',
    selected: false, focus() {}, select() { this.selected = true; },
    setSelectionRange(start, end) { this.selection = [start, end]; } };
  const status = { textContent: '' };
  const panel = { querySelector: (selector) => selector === 'textarea' ? citation : status };
  const button = { hidden: true, textContent: 'Copy', closest: () => panel,
    getAttribute: (name) => attrs[name], setAttribute: (name, value) => { attrs[name] = value; },
    addEventListener: (name, callback) => { events[name] = callback; } };
  return { button, citation, status, attrs, click: () => events.click() };
}

test('Copy preserves the complete citation and its accessible confirmation', async () => {
  const control = copyButton();
  const env = environment({ '[data-copy-citation]': [control.button] });
  let copied;
  env.context.navigator.clipboard = { async writeText(value) { copied = value; } };
  vm.runInNewContext(source, env.context);
  await control.click();
  assert.equal(copied, control.citation.value);
  assert.equal(control.status.textContent, 'Copied to clipboard.');
  assert.equal(control.attrs['aria-label'], 'Copied BibTeX for Example paper');
  env.timers[0]();
  assert.equal(control.button.textContent, 'Copy');
  assert.equal(control.attrs['aria-label'], 'Copy BibTeX for Example paper');
});

for (const legacyWorks of [true, false]) {
  test(`Clipboard denial keeps ${legacyWorks ? 'legacy copying' : 'manual selection'} usable`, async () => {
    const control = copyButton();
    const env = environment({ '[data-copy-citation]': [control.button] });
    env.context.navigator.clipboard = { async writeText() { throw new Error('Permission denied'); } };
    env.document.execCommand = () => legacyWorks;
    vm.runInNewContext(source, env.context);
    await control.click();
    assert.equal(control.citation.selected, true);
    assert.deepEqual(control.citation.selection, [0, control.citation.value.length]);
    assert.equal(control.status.textContent, legacyWorks ? 'Copied to clipboard.' : 'Citation selected. Touch and hold to copy.');
    assert.equal(control.button.textContent, legacyWorks ? 'Copied' : 'Copy');
  });
}

test('Topic filtering updates pressed state and the screen-reader announcement', () => {
  const events = {};
  const button = { dataset: { topic: 'health' }, textContent: 'Health economics',
    setAttribute(name, value) { this[name] = value; },
    addEventListener(name, callback) { events[name] = callback; } };
  const papers = [{ dataset: { topics: 'health' } }, { dataset: { topics: 'inflation' } }];
  const status = { textContent: '' };
  const env = environment({ '[data-topic]': [button], '[data-topics]': papers, '[data-filter-status]': [status] });
  vm.runInNewContext(source, env.context);
  events.click();
  assert.equal(button['aria-pressed'], 'true');
  assert.deepEqual(papers.map((p) => p.hidden), [false, true]);
  assert.equal(status.textContent, 'Showing 1 result for Health economics.');
});

test('The swipe cue disappears at the end and stays hidden on desktop', () => {
  const events = {};
  const tabs = { scrollWidth: 800, clientWidth: 320, scrollLeft: 0,
    addEventListener(name, callback) { events[name] = callback; } };
  const cue = { hidden: true };
  const strip = { querySelector: (selector) => selector === '.research-topics' ? tabs : cue };
  const env = environment({ '.topic-strip': [strip] });
  env.context.window.addEventListener = (name, callback) => { events[name] = callback; };
  vm.runInNewContext(source, env.context);
  assert.equal(cue.hidden, false);
  tabs.scrollLeft = 480;
  events.scroll();
  assert.equal(cue.hidden, true);
  tabs.scrollLeft = 0;
  events.scroll();
  assert.equal(cue.hidden, false);
  env.context.innerWidth = 1280;
  events.resize();
  assert.equal(cue.hidden, true);
});
