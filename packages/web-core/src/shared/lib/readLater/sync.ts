import {
  readLaterKey,
  type createReadLaterStore,
  type ReadLaterItem,
} from '@/shared/stores/useReadLaterStore';

type Store = ReturnType<typeof createReadLaterStore>;
type Record = { item: ReadLaterItem; saved: boolean };
export type ReadLaterTransport = {
  list: () => Promise<Record[]>;
  import: (items: ReadLaterItem[]) => Promise<void>;
  set: (item: ReadLaterItem, saved: boolean, changeId: string) => Promise<void>;
};

/** One serialized stream per host/user; optimistic pending actions survive reloads. */
export class ReadLaterSync {
  private running: Promise<void> | undefined;
  private failed = false;
  constructor(
    private store: Store,
    private scope: string,
    private transport: ReadLaterTransport,
    private isOnline: () => boolean = () => true
  ) {}

  refresh(): Promise<void> {
    if (this.running) return this.running;
    this.running = this.run().finally(() => {
      this.running = undefined;
      // An action can arrive during the final GET. Do not wait for the next poll.
      if (!this.failed && this.pending().length) void this.refresh();
    });
    return this.running;
  }

  private pending() {
    return Object.entries(this.store.getState().pending).filter(
      ([key, value]) =>
        key === readLaterKey(this.scope, value.item.kind, value.item.id)
    );
  }

  private async run() {
    try {
      this.failed = false;
      if (!this.isOnline()) throw new Error('offline');
      // Probe the capability before touching the browser's legacy cache.
      let records = await this.transport.list();
      if (!this.store.getState().migratedScopes[this.scope]) {
        const local = Object.entries(this.store.getState().items)
          .filter(
            ([key, item]) =>
              key === readLaterKey(this.scope, item.kind, item.id)
          )
          .map(([, item]) => item);
        await this.transport.import(local);
        records = await this.transport.list();
        this.store.setState((state) => ({
          migratedScopes: { ...state.migratedScopes, [this.scope]: true },
        }));
      }
      this.store.getState().applyServer(this.scope, records);
      while (this.pending().length) {
        for (const [key, value] of this.pending()) {
          await this.transport.set(value.item, value.later, value.changeId);
          this.store.getState().acknowledge(key, value.changeId);
        }
      }
      this.store
        .getState()
        .applyServer(this.scope, await this.transport.list());
      if (!this.isOnline()) throw new Error('offline');
      this.store.setState((state) => ({
        syncErrors: { ...state.syncErrors, [this.scope]: '' },
      }));
    } catch {
      this.failed = true;
      // Keep both local choices and queued actions; reconnect retries safely.
      this.store.setState((state) => ({
        syncErrors: {
          ...state.syncErrors,
          [this.scope]:
            'Read Later has not synced. Your choices are saved in this browser and will retry when connected.',
        },
      }));
    }
  }
}
