// Real shared renderer/container, isolated messages and clipboard; no live writes.
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';
import {
  bundleNotifications,
  state,
  transport,
  wait,
} from './notification-test-support.mjs';
const parsed = await build({
  entryPoints: ['packages/ui/src/lib/dot-code-blocks.ts'],
  bundle: true,
  write: false,
  format: 'esm',
});
const { splitDotMessage } = await import(
  'data:text/javascript;base64,' +
    Buffer.from(parsed.outputFiles[0].text).toString('base64')
);
const exact =
  '  const message = "<img src=x onerror=alert(1)>";\r\n\t// keep tabs and spaces  \r\n\r\n';
const body =
  'Before <script>alert(1)</script>\n```javascript\r\n' +
  exact +
  '```\r\nAfter <b>ordinary text</b>\n~~~mystery-lang\n<svg onload=alert(1)>\n~~~\n```\n```';
const parts = splitDotMessage(body);
assert.deepEqual(
  parts.map((p) => p.kind),
  ['text', 'code', 'text', 'code', 'code']
);
assert.equal(parts[1].text, exact);
assert.equal(parts[3].language, 'mystery-lang');
assert.equal(parts[4].text, '');
assert.equal(splitDotMessage('  ````ts\nx\n```\n`````\n')[0].text, 'x\n```\n');
assert.equal(splitDotMessage('```py\nx\n')[0].text, 'x\n');
assert.equal(
  splitDotMessage('before `inline`\n    ```js\nplain')[0].text,
  'before `inline`\n    ```js\nplain'
);
assert.equal(splitDotMessage('```bad`info\ntext')[0].kind, 'text');
assert.equal(splitDotMessage('~~~\rx\r~~~')[0].text, 'x\r');
const bundle = await bundleNotifications();
for (const project of [false, true]) {
  const s = {
    ...state(),
    supportsReplies: true,
    messages: [
      {
        id: 'dot-reply',
        seq: 2,
        role: 'dot',
        workspace: '11111111-1111-4111-8111-111111111111',
        body,
        created: 1792321200,
        seen: false,
        manual_unread: true,
        attention: { kind: 'question', resolved: false },
      },
    ],
  };
  const original = JSON.stringify(s.messages),
    copies = [];
  let deny = false;
  let hold = false;
  let releaseCopy;
  const dom = new JSDOM('<div id="root"></div>', {
    url: 'https://fixture.invalid/' + (project ? '?project' : ''),
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    beforeParse(w) {
      w.matchMedia = () => ({
        matches: false,
        addEventListener() {},
        removeEventListener() {},
      });
      w.CSS = { escape: (x) => x };
      w.document.hasFocus = () => false;
      w.HTMLElement.prototype.scrollIntoView = function () {};
      w.fetch = transport(s);
      Object.defineProperty(w.navigator, 'clipboard', {
        value: {
          writeText: async (text) => {
            if (deny) throw Error('Denied');
            if (hold)
              await new Promise((resolve) => {
                releaseCopy = resolve;
              });
            copies.push(text);
          },
        },
      });
    },
  });
  try {
    dom.window.eval(bundle.js);
    await wait(() => dom.window.document.querySelector('#message-dot-reply'));
    const d = dom.window.document;
    d.getElementById('toggle-dot').click();
    const blocks = [...d.querySelectorAll('.dot-code-block')];
    assert.equal(blocks.length, 3);
    assert.equal(blocks[0].querySelector('code').textContent, exact);
    assert.ok(
      blocks[0].querySelector('code span'),
      'Known language highlighted'
    );
    assert.equal(
      blocks[1].querySelector('code span'),
      null,
      'Unknown stays neutral'
    );
    assert.equal(
      d.querySelector(
        '.dot-message script,.dot-message img,.dot-message svg,.dot-message b'
      ),
      null
    );
    assert.ok(
      d.querySelector('.dot-message p').textContent.includes('<script>')
    );
    for (let i = 0; i < blocks.length; i++) {
      blocks[i].querySelector('button').click();
      await wait(() => blocks[i].textContent.includes('Code copied'));
    }
    assert.deepEqual(copies, [exact, '<svg onload=alert(1)>\n', '']);
    deny = true;
    blocks[0].querySelector('button').click();
    await wait(() => blocks[0].textContent.includes('Could not copy.'));
    assert.equal(blocks[0].querySelector('button').disabled, false);
    deny = false;
    blocks[0].querySelector('button').click();
    await wait(() => blocks[0].textContent.includes('Code copied'));
    assert.equal(copies.at(-1), exact);
    d.querySelector('.dot-reply-button').click();
    await wait(() => d.querySelector('.dot-reply-target'));
    assert.ok(
      d
        .querySelector('.dot-reply-target')
        .textContent.includes('Before <script>')
    );
    assert.equal(d.querySelector('.dot-reply-target script'), null);
    [...d.querySelectorAll('button')]
      .find((b) => b.textContent === 'Jump to Needs Attention')
      .click();
    await wait(() => d.querySelector('[data-dot-attention-current]'));
    assert.equal(
      JSON.stringify(s.messages),
      original,
      'Copy/reply/navigation do not mutate stored body/read/attention'
    );
    assert.equal(s.readStates.length, 0);
    assert.equal(s.reads.length, 0);
    hold = true;
    blocks[0].querySelector('button').click();
    await wait(() => releaseCopy);
    // New history/updated body invalidates feedback from an old in-flight copy.
    s.messages = [
      { ...s.messages[0], body: '```python\nprint("updated")\n```' },
    ];
    d.querySelector('[aria-label="Refresh conversation"]').click();
    await wait(
      () =>
        d.querySelector('.dot-code-block code')?.textContent ===
        'print("updated")\n'
    );
    releaseCopy();
    hold = false;
    await wait(() => copies.at(-1) === exact);
    assert.equal(
      d.querySelector('.dot-code-toolbar button').textContent,
      'Copy'
    );
    const large = 'z'.repeat(50_001) + '\n';
    s.messages = [
      { ...s.messages[0], body: '```javascript\n' + large + '```' },
    ];
    d.querySelector('[aria-label="Refresh conversation"]').click();
    await wait(
      () => d.querySelector('.dot-code-block code')?.textContent === large
    );
    assert.equal(d.querySelector('.dot-code-block code span'), null);
    d.querySelector('.dot-code-toolbar button').click();
    await wait(() => copies.at(-1) === large);
    console.log(
      'PASS shared code renderer, exact copy/failure/retry, safety, update and state independence',
      project ? 'project' : 'workspace'
    );
  } finally {
    dom.window.close();
  }
}
