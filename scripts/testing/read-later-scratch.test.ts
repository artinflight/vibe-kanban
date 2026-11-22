import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { Scratch } from 'shared/types';
import {
  createScratchReadLaterTransport,
  type ScratchReadLaterIO,
} from '../../packages/web-core/src/shared/lib/readLater/scratchTransport';
import {
  createReadLaterStore,
  readLaterKey,
} from '../../packages/web-core/src/shared/stores/useReadLaterStore';
import { ReadLaterSync } from '../../packages/web-core/src/shared/lib/readLater/sync';
const item = {
  kind: 'workspace' as const,
  id: 'example-workspace',
  name: 'Example workspace',
};
const scope = '["local","example-user"]';
const key = readLaterKey(scope, item.kind, item.id);
function fixture() {
  const rows = new Map<string, Scratch>();
  let loseResponse = false;
  let failGet = false;
  const io: ScratchReadLaterIO = {
    list: async () => structuredClone([...rows.values()]),
    get: async (id) => {
      if (failGet) {
        failGet = false;
        throw Error('network');
      }
      const row = rows.get(id);
      if (!row) throw Error('missing');
      return structuredClone(row);
    },
    create: async (id, content) => {
      if (rows.has(id)) throw Error('duplicate');
      rows.set(id, {
        id,
        payload: { type: 'WORKSPACE_NOTES', data: { content } },
        created_at: '',
        updated_at: '',
      });
      if (loseResponse) {
        loseResponse = false;
        failGet = true;
        throw Error('response lost');
      }
    },
  };
  return {
    rows,
    io,
    lose: () => {
      loseResponse = true;
    },
    client: (user = 'example-user') => createScratchReadLaterTransport(user, io),
  };
}

test('existing scratch wire protocol shares saves and removals without touching user notes', async () => {
  const f = fixture();
  const userNote: Scratch = {
    id: crypto.randomUUID(),
    payload: {
      type: 'WORKSPACE_NOTES',
      data: { content: 'Actual workspace note' },
    },
    created_at: '',
    updated_at: '',
  };
  f.rows.set(userNote.id, userNote);
  const a = f.client(),
    b = f.client();
  await a.list();
  await b.list();
  await a.set(item, true, 'desktop-save');
  assert.equal((await b.list())[0].saved, true);
  await b.set(item, false, 'mobile-remove');
  assert.equal((await a.list())[0].saved, false);
  await f.client().import([item]);
  assert.equal(
    (await a.list())[0].saved,
    false,
    'stale legacy import cannot defeat a tombstone'
  );
  assert.deepEqual(f.rows.get(userNote.id), userNote);
  assert.deepEqual(await f.client('different-user').list(), []);
});

test('concurrent independent edits and same-item ties converge in every browser', async () => {
  const f = fixture(),
    a = f.client(),
    b = f.client();
  await Promise.all([a.list(), b.list()]);
  await Promise.all([
    a.set(item, true, 'a'),
    b.set({ kind: 'issue', id: 'other' }, true, 'b'),
  ]);
  assert.equal((await a.list()).filter((r) => r.saved).length, 2);
  await b.list();
  await Promise.all([a.set(item, false, 'remove'), b.set(item, true, 'save')]);
  assert.deepEqual(await a.list(), await b.list());
  assert.equal(
    f.rows.size,
    4,
    'each intent is immutable; independent records survive'
  );
});

test('lost response plus browser reload cannot replay a save over a later removal', async () => {
  const f = fixture();
  const desktop = createReadLaterStore(
    'scratch-desktop-' + crypto.randomUUID()
  );
  const a = new ReadLaterSync(desktop, scope, f.client());
  await a.refresh();
  desktop.getState().setReadLater(scope, item, true);
  f.lose();
  await a.refresh();
  assert.ok(desktop.getState().pending[key]);
  const mobile = f.client();
  await mobile.list();
  await mobile.set(item, false, 'remove-after-lost-response');
  const reload = createReadLaterStore(desktop.persist.getOptions().name);
  await new ReadLaterSync(reload, scope, f.client()).refresh();
  assert.equal(reload.getState().items[key], undefined);
  assert.equal(Object.keys(reload.getState().pending).length, 0);
  assert.equal(
    f.rows.size,
    2,
    'retry acknowledged the original insert without replay'
  );
});

test('racing legacy imports use insert-only IDs and always lose to an explicit removal', async () => {
  const f = fixture(),
    stale = f.client(),
    current = f.client();
  await Promise.all([stale.list(), current.list()]);
  await current.set(item, false, 'explicit-remove');
  await Promise.all([
    stale.import([item]),
    f.client().import([{ ...item, name: 'old title' }]),
  ]);
  assert.equal((await current.list())[0].saved, false);
  assert.equal(
    f.rows.size,
    2,
    'duplicate imports reconcile the same immutable record'
  );
});
