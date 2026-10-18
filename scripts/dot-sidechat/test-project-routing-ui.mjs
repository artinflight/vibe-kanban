import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import {
  projectRoutingBundle,
  routingState,
  routingTransport,
  deferred,
  ids,
} from './project-routing-test-support.mjs';
import { wait } from './notification-test-support.mjs';
const bundle = await projectRoutingBundle();
for (const width of [390, 1440]) {
  const s = routingState();
  function mount(saved = []) {
    const dom = new JSDOM('<div id="root"></div>', {
      url: 'https://fixture.invalid/projects/' + ids.project,
      runScripts: 'dangerously',
      pretendToBeVisual: true,
      beforeParse(w) {
        w.matchMedia = () => ({
          matches: width < 768,
          addEventListener() {},
          removeEventListener() {},
        });
        w.fetch = routingTransport(s);
        w.document.hasFocus = () => false;
        w.CSS = { escape: (x) => x };
        w.ResizeObserver = class {
          constructor(fn) {
            this.fn = fn;
          }
          observe() {
            this.fn();
          }
          disconnect() {}
        };
        w.HTMLElement.prototype.getBoundingClientRect = function () {
          return {
            top: 0,
            left: 0,
            right: width,
            bottom: 900,
            width,
            height: 900,
          };
        };
        w.HTMLElement.prototype.scrollIntoView = function () {};
        w.HTMLElement.prototype.setPointerCapture = function () {};
        w.HTMLElement.prototype.releasePointerCapture = function () {};
        for (const [k, v] of saved) w.sessionStorage.setItem(k, v);
      },
    });
    dom.window.eval(bundle.js);
    return dom;
  }
  let dom = mount();
  try {
    let doc = dom.window.document;
    const button = (label) =>
      [...doc.querySelectorAll('button')].find(
        (b) =>
          b.textContent.trim() === label ||
          b.getAttribute('aria-label') === label
      );
    const input = () => doc.getElementById('dot-draft');
    async function open() {
      await wait(() => button('Open project sidebar'));
      if (
        button('Open project sidebar').getAttribute('aria-expanded') !== 'true'
      )
        button('Open project sidebar').click();
      await wait(() => input());
    }
    async function ready(d) {
      await open();
      await wait(
        () =>
          doc
            .querySelector('.dot-scope')
            ?.textContent.includes(
              d === 'project' ? 'Project-wide' : 'Workspace ' + d
            ) && doc.querySelector('.dot-history #message-note-' + d)
      );
    }
    const type = (value) => {
      Object.getOwnPropertyDescriptor(
        dom.window.HTMLTextAreaElement.prototype,
        'value'
      ).set.call(input(), value);
      input().dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    };
    const route = async (d) => {
      dom.window.fixtureNavigate(d);
      await wait(
        () =>
          doc.getElementById('displayed-workspace')?.textContent ===
          (d === 'project' ? 'Project board' : 'Displayed workspace ' + d)
      );
    };
    await ready('project');
    type('Project draft');
    doc.querySelector('[aria-label="Reply to message 1"]').click();
    button('Jump to Needs Attention').click();
    await wait(
      () =>
        doc.querySelector('.dot-reply-target') &&
        doc.querySelector('[data-dot-attention-current]')
    );
    const node = input();
    if (width >= 768) {
      let handle = doc.querySelector('[aria-label="Resize project sidebar"]');
      handle.dispatchEvent(
        new dom.window.KeyboardEvent('keydown', {
          key: 'ArrowLeft',
          bubbles: true,
        })
      );
      await wait(() => handle.getAttribute('aria-valuenow') === '444');
      button('Full-width chat').click();
      await wait(() => doc.querySelector('.project-space-board').hidden);
      assert.equal(input(), node);
      assert.equal(input().value, 'Project draft');
      assert.ok(doc.querySelector('.dot-reply-target'));
      assert.ok(doc.querySelector('[data-dot-attention-current]'));
      button('Restore sidebar width').click();
      await wait(
        () =>
          doc
            .querySelector('[aria-label="Resize project sidebar"]')
            ?.getAttribute('aria-valuenow') === '444'
      );
      assert.equal(input(), node);
      assert.equal(doc.querySelector('.project-space-board').hidden, false);
      handle = doc.querySelector('[aria-label="Resize project sidebar"]');
      handle.dispatchEvent(
        new dom.window.MouseEvent('pointerdown', {
          clientX: 800,
          button: 0,
          bubbles: true,
        })
      );
      handle.dispatchEvent(
        new dom.window.MouseEvent('pointermove', {
          clientX: 700,
          bubbles: true,
        })
      );
      await wait(() => handle.getAttribute('aria-valuenow') === '544');
      handle.dispatchEvent(
        new dom.window.MouseEvent('pointerup', { bubbles: true })
      );
    } else {
      assert.equal(
        doc.querySelector('[aria-label="Resize project sidebar"]'),
        null
      );
      assert.equal(button('Full-width chat'), undefined);
    }
    const holdA = deferred();
    s.threadHolds.set('a', holdA);
    await route('a');
    await open();
    await wait(() =>
      s.requests.some((r) => r.url.includes('workspace=' + ids.a))
    );
    assert.equal(
      doc.querySelector('.dot-history #message-note-project'),
      null,
      'Old destination history disappears immediately'
    );
    assert.ok(doc.querySelector('button[type="submit"]').disabled);
    await route('b');
    await ready('b');
    type('B draft');
    s.threadHolds.delete('a');
    holdA.resolve();
    await new Promise((r) => setTimeout(r, 30));
    assert.ok(
      doc.querySelector('.dot-scope').textContent.includes('Workspace b')
    );
    assert.equal(input().value, 'B draft');
    assert.equal(
      doc.querySelector('#message-note-a'),
      null,
      'Late response cannot replace B'
    );
    await route('a');
    await ready('a');
    assert.equal(input().value, '');
    type('A exact reply');
    doc.querySelector('[aria-label="Reply to message 1"]').click();
    const sendHold = deferred();
    s.sendHolds.set('a', sendHold);
    await wait(() => !doc.querySelector('button[type="submit"]').disabled);
    doc.querySelector('button[type="submit"]').click();
    await wait(() => s.sends.length === 1);
    const original = s.sends[0];
    assert.equal(original.workspace, ids.a);
    assert.equal(original.project, undefined);
    assert.equal(original.in_reply_to, 'note-a');
    await route('b');
    await ready('b');
    assert.equal(input().value, 'B draft');
    sendHold.resolve(503);
    s.sendHolds.delete('a');
    await new Promise((r) => setTimeout(r, 30));
    assert.equal(input().value, 'B draft');
    await route('a');
    await ready('a');
    await wait(() => input().readOnly);
    assert.equal(input().value, 'A exact reply');
    doc.querySelector('button[type="submit"]').click();
    await wait(() => s.sends.length === 2 && input().value === '');
    assert.deepEqual(
      s.sends[1],
      original,
      'Retry retains exact destination/body/reply/key'
    );
    const successHold = deferred();
    s.sendHolds.set('a', successHold);
    type('Ordinary A after reply');
    await wait(() => !doc.querySelector('button[type="submit"]').disabled);
    doc.querySelector('button[type="submit"]').click();
    await wait(() => s.sends.length === 3);
    assert.equal(s.sends[2].in_reply_to, undefined);
    await route('b');
    await ready('b');
    successHold.resolve(200);
    s.sendHolds.delete('a');
    await new Promise((r) => setTimeout(r, 30));
    assert.equal(
      input().value,
      'B draft',
      'Late successful A send cannot clear B draft'
    );
    await route('a');
    await ready('a');
    assert.equal(input().value, '');
    await route('project');
    await ready('project');
    assert.equal(input().value, 'Project draft');
    assert.match(
      doc.querySelector('.dot-reply-target').textContent,
      /Conversation project/
    );
    dom.window.history.back();
    if (width < 768) {
      await wait(() => !input());
      dom.window.history.back();
    }
    await wait(
      () =>
        doc.getElementById('displayed-workspace')?.textContent ===
        'Displayed workspace a'
    );
    await ready('a');
    assert.equal(input().value, '');
    assert.equal(doc.querySelector('.dot-reply-target'), null);
    await route('project');
    await ready('project');
    const saved = Array.from(
      { length: dom.window.sessionStorage.length },
      (_, i) => {
        const key = dom.window.sessionStorage.key(i);
        return [key, dom.window.sessionStorage.getItem(key)];
      }
    );
    dom.window.close();
    dom = mount(saved);
    doc = dom.window.document;
    await ready('project');
    assert.equal(input().value, 'Project draft');
    assert.match(
      doc.querySelector('.dot-reply-target').textContent,
      /Conversation project/
    );
    const write = dom.window.Storage.prototype.setItem;
    dom.window.Storage.prototype.setItem = () => {
      throw Error('Synthetic quota failure');
    };
    type('Quota retained project draft');
    await route('b');
    await ready('b');
    await route('project');
    await ready('project');
    assert.equal(input().value, 'Quota retained project draft');
    dom.window.Storage.prototype.setItem = write;
    assert.ok(s.sends.every((m) => m.workspace === ids.a && !m.project));
    console.log(
      `PASS project routing ${width}: exact workspace/shared issue context, late GET, rapid switches, close/Back, per-destination drafts/reply+reload, in-flight send/retry isolation, resize/full restore keeps state.`
    );
  } finally {
    dom.window.close();
  }
}
