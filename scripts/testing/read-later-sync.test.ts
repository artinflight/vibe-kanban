import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  createReadLaterStore,
  readLaterKey,
  type ReadLaterItem,
} from '../../packages/web-core/src/shared/stores/useReadLaterStore';
import {
  ReadLaterSync,
  type ReadLaterTransport,
} from '../../packages/web-core/src/shared/lib/readLater/sync';

const scope = JSON.stringify(['local', 'owner']);
const premiere: ReadLaterItem = {
  kind: 'workspace',
  id: 'premiere',
  name: 'Premiere Pro to mobile',
};
const key = readLaterKey(scope, premiere.kind, premiere.id);
function fixture() {
  const records = new Map<string, { item: ReadLaterItem; saved: boolean }>();
  const receipts = new Set<string>();
  let offline = false;
  let loseResponse = false;
  const transport: ReadLaterTransport = {
    list: async () => {
      if (offline) throw Error('offline');
      return structuredClone([...records.values()]);
    },
    import: async (items) => {
      for (const item of items) {
        const id = item.kind + item.id;
        if (!records.has(id)) records.set(id, { item, saved: true });
      }
    },
    set: async (item, saved, changeId) => {
      if (offline) throw Error('offline');
      if (!receipts.has(changeId)) {
        receipts.add(changeId);
        records.set(item.kind + item.id, { item, saved });
      }
      if (loseResponse) {
        loseResponse = false;
        throw Error('response lost');
      }
    },
  };
  const desktop = createReadLaterStore('sync-desktop-' + crypto.randomUUID());
  const mobile = createReadLaterStore('sync-mobile-' + crypto.randomUUID());
  return {
    desktop,
    mobile,
    a: new ReadLaterSync(desktop, scope, transport),
    b: new ReadLaterSync(mobile, scope, transport),
    transport,
    offline: (value: boolean) => {
      offline = value;
    },
    loseResponse: () => {
      loseResponse = true;
    },
  };
}

test('two independent browser stores share saves/removals and migrate legacy desktop choices', async () => {
  const f = fixture();
  f.desktop.setState({ items: { [key]: premiere } }); // old v1 cache, no queued action
  await f.a.refresh();
  await f.b.refresh();
  assert.deepEqual(f.mobile.getState().items[key], premiere);
  f.mobile.getState().setReadLater(scope, premiere, false);
  await f.b.refresh();
  await f.a.refresh();
  assert.equal(f.desktop.getState().items[key], undefined);
  const stale = createReadLaterStore('stale-' + crypto.randomUUID());
  stale.setState({ items: { [key]: premiere } });
  await new ReadLaterSync(stale, scope, f.transport).refresh();
  assert.equal(
    stale.getState().items[key],
    undefined,
    'old browser import respects removal'
  );
  f.mobile.getState().setReadLater(scope, premiere, true);
  await f.b.refresh();
  await f.a.refresh();
  assert.ok(f.desktop.getState().items[key]);
});

test('offline choices survive reload and synchronize after reconnect', async () => {
  const f = fixture();
  await f.a.refresh();
  f.offline(true);
  f.desktop.getState().setReadLater(scope, premiere, true);
  await f.a.refresh();
  assert.ok(f.desktop.getState().pending[key]);
  assert.ok(f.desktop.getState().syncErrors[scope]);
  const reloaded = createReadLaterStore(f.desktop.persist.getOptions().name);
  assert.ok(reloaded.getState().items[key]);
  assert.ok(reloaded.getState().pending[key]);
  const reconnect = new ReadLaterSync(reloaded, scope, f.transport);
  f.offline(false);
  await reconnect.refresh();
  await f.b.refresh();
  assert.ok(f.mobile.getState().items[key]);
  assert.equal(Object.keys(reloaded.getState().pending).length, 0);
  assert.equal(reloaded.getState().syncErrors[scope], '');
});

test('lost save response cannot replay over a later mobile removal', async () => {
  const f = fixture();
  await f.a.refresh();
  await f.b.refresh();
  f.desktop.getState().setReadLater(scope, premiere, true);
  f.loseResponse();
  await f.a.refresh();
  assert.ok(f.desktop.getState().pending[key]);
  f.mobile.getState().setReadLater(scope, premiere, false);
  await f.b.refresh();
  await f.a.refresh();
  assert.equal(f.desktop.getState().items[key], undefined);
  assert.equal(f.mobile.getState().items[key], undefined);
});

test('an in-flight save preserves a newer local removal and independent bookmarks', async () => {
  const f = fixture();
  await f.a.refresh();
  let release!: () => void;
  const barrier = new Promise<void>((resolve) => {
    release = resolve;
  });
  const transport = {
    ...f.transport,
    set: async (item: ReadLaterItem, saved: boolean, id: string) => {
      await barrier;
      await f.transport.set(item, saved, id);
    },
  };
  const a = new ReadLaterSync(f.desktop, scope, transport);
  f.desktop.getState().setReadLater(scope, premiere, true);
  const running = a.refresh();
  await new Promise((resolve) => setTimeout(resolve, 0));
  f.desktop.getState().setReadLater(scope, premiere, false);
  f.mobile
    .getState()
    .setReadLater(scope, { kind: 'issue', id: 'another' }, true);
  await f.b.refresh();
  release();
  await running;
  await f.b.refresh();
  assert.equal(f.mobile.getState().items[key], undefined);
  assert.ok(
    f.desktop.getState().items[readLaterKey(scope, 'issue', 'another')]
  );
});
