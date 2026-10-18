// Real container + Preserve's derived presentation contract, no live API/browser.
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import {
  bundleNotifications,
  state,
  transport,
  wait,
} from './notification-test-support.mjs';
const bundle = await bundleNotifications();
const workspace = '11111111-1111-4111-8111-111111111111';
for (const project of [false, true])
  for (const width of [390, 1440]) {
    const raw = 'Dot prompted this workspace: RAW-IMMUTABLE-AUDIT';
    const neutral =
      'The workspace agent was prompted. Caller: unknown. <b>plain text</b>';
    const note = {
      id: 'dispatch-exact',
      seq: 1,
      role: 'dot',
      body: raw,
      hash: 'retained-hash',
      workspace,
      created: 1792281600,
      seen: false,
      manual_unread: true,
      attention: { kind: 'question', resolved: false },
      dispatch_note: {
        workspace_id: workspace,
        execution_id: 'synthetic-execution',
        ownership_signal: false,
        presentation: {
          author_label: 'Dispatch',
          body: neutral,
          derived: true,
          stored_message_unchanged: true,
        },
      },
    };
    const reference = {
      id: note.id,
      seq: 1,
      role: 'dot',
      created: note.created,
      excerpt: raw,
      truncated: false,
    };
    const genuine = {
      ...note,
      id: 'genuine-exact',
      seq: 2,
      body: 'Dot prompted a genuine conversation, unchanged.',
      dispatch_note: undefined,
    };
    const reply = {
      id: 'owner-exact',
      seq: 3,
      role: 'owner',
      workspace,
      created: note.created,
      body: 'Owner follow-up',
      in_reply_to: note.id,
      reply_reference: reference,
    };
    const unavailable = {
      ...reply,
      id: 'unavailable-exact',
      seq: 4,
      reply_reference: {
        ...reference,
        unavailable: true,
        excerpt: 'PRIVATE-QUOTE-MUST-NOT-LEAK',
      },
    };
    const owner = {
      ...reply,
      id: 'owner-ordinary',
      seq: 5,
      reply_reference: undefined,
      body: 'Owner original text',
      dispatch_note: note.dispatch_note,
    };
    const s = {
      ...state(),
      supportsReplies: true,
      messages: [note, genuine, reply, unavailable, owner],
    };
    const before = JSON.stringify(s.messages);
    const sends = [];
    const base = transport(s);
    const dom = new JSDOM('<div id="root"></div>', {
      url: 'https://fixture.invalid/' + (project ? '?project' : ''),
      runScripts: 'dangerously',
      pretendToBeVisual: true,
      beforeParse(w) {
        w.matchMedia = () => ({
          matches: width < 768,
          addEventListener() {},
          removeEventListener() {},
        });
        w.CSS = { escape: (x) => x };
        w.document.hasFocus = () => false;
        w.HTMLElement.prototype.scrollIntoView = function () {};
        w.fetch = async (url, opts = {}) => {
          if (url === '/api/dot-sidechat/send') {
            const body = JSON.parse(opts.body);
            sends.push(body);
            assert.equal(body.in_reply_to, note.id);
            return {
              ok: true,
              status: 200,
              json: async () => ({ id: 'saved-exact' }),
            };
          }
          return base(url, opts);
        };
      },
    });
    try {
      dom.window.eval(bundle.js);
      const doc = dom.window.document;
      await wait(() => doc.querySelector('#message-dispatch-exact'));
      doc.getElementById('toggle-dot').click();
      const article = (id) => doc.getElementById('message-' + id);
      assert.equal(
        article(note.id).querySelector('strong').textContent,
        'Dispatch'
      );
      assert.equal(article(note.id).querySelector('p').textContent, neutral);
      assert.equal(
        article(note.id).querySelector('b'),
        null,
        'Presentation stays plain text'
      );
      assert.equal(
        article(genuine.id).querySelector('strong').textContent,
        'Dot'
      );
      assert.equal(
        article(genuine.id).querySelector('p').textContent,
        genuine.body
      );
      assert.equal(
        article(owner.id).querySelector('strong').textContent,
        'You'
      );
      assert.equal(
        article(owner.id).querySelector('p').textContent,
        owner.body
      );
      const quote = article(reply.id).querySelector('blockquote');
      assert.match(quote.textContent, /Reply to Dispatch/);
      assert.ok(quote.textContent.includes(neutral));
      assert.ok(quote.querySelector('a').href.endsWith('&message=' + note.id));
      assert.match(
        article(unavailable.id).textContent,
        /context in another workspace/
      );
      assert.ok(!doc.body.textContent.includes('PRIVATE-QUOTE-MUST-NOT-LEAK'));
      assert.ok(!doc.querySelector('.dot-history').textContent.includes(raw));
      assert.equal(
        doc.querySelector('[data-dot-managed]'),
        null,
        'Dispatch never establishes management'
      );
      article(note.id).querySelector('.dot-reply-button').click();
      await wait(() => doc.querySelector('.dot-reply-target'));
      assert.match(
        doc.querySelector('.dot-reply-target').textContent,
        /Replying to Dispatch/
      );
      assert.equal(
        doc.querySelector('.dot-reply-target p').textContent,
        neutral
      );
      doc.querySelector('[aria-label="Cancel reply"]').click();
      await wait(() => !doc.querySelector('.dot-reply-target'));
      article(note.id).querySelector('.dot-reply-button').click();
      const input = doc.getElementById('dot-draft');
      Object.getOwnPropertyDescriptor(
        dom.window.HTMLTextAreaElement.prototype,
        'value'
      ).set.call(input, 'Reply to exact dispatch');
      input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
      await wait(() => !doc.querySelector('button[type="submit"]').disabled);
      doc.querySelector('button[type="submit"]').click();
      await wait(
        () => sends.length === 1 && !doc.querySelector('.dot-reply-target')
      );
      assert.equal(sends[0].in_reply_to, note.id);
      assert.equal(
        JSON.stringify(s.messages),
        before,
        'Raw IDs/role/body/hash/order/flags untouched'
      );
      assert.ok(s.requests.every((r) => r.method === 'GET'));
      assert.deepEqual(
        [...doc.querySelectorAll('.dot-history article')].map((n) => n.id),
        s.messages.map((m) => 'message-' + m.id)
      );
      console.log(
        `PASS dispatch presentation ${project ? 'project' : 'issue'} ${width}: neutral message/history/composer; exact reply ID; raw state/genuine conversation/privacy/management preserved.`
      );
    } finally {
      dom.window.close();
    }
  }
