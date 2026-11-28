import type { Scratch } from 'shared/types';
import type { ReadLaterItem } from '@/shared/stores/useReadLaterStore';
import type { ReadLaterTransport } from './sync';

// Dedicated immutable records, never actual workspace-note IDs or user preferences.
// WORKSPACE_NOTES is the existing scratch API's opaque string envelope. Keeping
// the wire format compatible lets this frontend ship without a backend restart.
export const READ_LATER_SCRATCH_PREFIX = '7ead1a7e-';
const format = 'vk.read-later.event.v1';
type Event = {
  format: typeof format;
  user: string;
  item: ReadLaterItem;
  saved: boolean;
  imported: boolean;
  changeId: string;
  clock: number;
};
export type ScratchReadLaterIO = {
  list: () => Promise<Scratch[]>;
  get: (id: string) => Promise<Scratch>;
  create: (id: string, content: string) => Promise<void>;
};
const key = (item: ReadLaterItem) => JSON.stringify([item.kind, item.id]);
const kinds = new Set(['workspace', 'project', 'issue', 'notification']);

function parse(row: Scratch, user: string): Event | undefined {
  if (
    !row.id.startsWith(READ_LATER_SCRATCH_PREFIX) ||
    row.payload.type !== 'WORKSPACE_NOTES'
  )
    return;
  try {
    const event = JSON.parse(row.payload.data.content) as Event;
    if (
      event.format === format &&
      event.user === user &&
      typeof event.changeId === 'string' &&
      typeof event.saved === 'boolean' &&
      typeof event.imported === 'boolean' &&
      Number.isSafeInteger(event.clock) &&
      event.clock >= 0 &&
      event.item &&
      kinds.has(event.item.kind) &&
      typeof event.item.id === 'string' &&
      event.item.id.length > 0 &&
      event.item.id.length <= 512 &&
      (event.item.name === undefined || typeof event.item.name === 'string') &&
      (event.item.projectId === undefined ||
        typeof event.item.projectId === 'string')
    )
      return event;
  } catch {
    // Other scratch notes and malformed/unowned records are never modified.
  }
}

async function eventId(user: string, changeId: string) {
  const digest = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(JSON.stringify([format, user, changeId]))
  );
  const h = Array.from(new Uint8Array(digest), (b) =>
    b.toString(16).padStart(2, '0')
  ).join('');
  return `${READ_LATER_SCRATCH_PREFIX}${h.slice(0, 4)}-5${h.slice(4, 7)}-a${h.slice(7, 10)}-${h.slice(10, 22)}`;
}

/** An append-only preference log: independent changes cannot overwrite each other. */
export function createScratchReadLaterTransport(
  user: string,
  io: ScratchReadLaterIO
): ReadLaterTransport {
  let events = new Map<string, Event>();
  let clock = 0;
  async function append(
    item: ReadLaterItem,
    saved: boolean,
    changeId: string,
    imported: boolean
  ) {
    const id = await eventId(user, changeId);
    const matches = (event: Event | undefined) =>
      event &&
      event.changeId === changeId &&
      key(event.item) === key(item) &&
      event.saved === saved &&
      event.imported === imported;
    if (events.has(id)) {
      if (!matches(events.get(id))) throw Error('Conflicting Read Later event');
      return; // A lost response/reload never replays over a later removal.
    }
    const event: Event = {
      format,
      user,
      item,
      saved,
      imported,
      changeId,
      clock: imported ? 0 : ++clock,
    };
    try {
      // POST inserts only. Never PUT/upsert an existing record or user note.
      await io.create(id, JSON.stringify(event));
    } catch (error) {
      // Reconcile an uncertain response or another tab's identical import.
      const existing = parse(await io.get(id), user);
      if (!matches(existing)) throw error;
      events.set(id, existing!);
      return;
    }
    events.set(id, event);
  }
  return {
    list: async () => {
      const next = new Map<string, Event>();
      for (const row of await io.list()) {
        const event = parse(row, user);
        if (event) {
          next.set(row.id, event);
          clock = Math.max(clock, event.clock);
        }
      }
      events = next;
      const winners = new Map<string, { id: string; event: Event }>();
      for (const [id, event] of events) {
        const old = winners.get(key(event.item));
        // Explicit choices always outrank legacy imports, including removals.
        if (
          !old ||
          (old.event.imported && !event.imported) ||
          (old.event.imported === event.imported &&
            (event.clock > old.event.clock ||
              (event.clock === old.event.clock && id > old.id)))
        )
          winners.set(key(event.item), { id, event });
      }
      return [...winners.values()].map(({ event }) => ({
        item: event.item,
        saved: event.saved,
      }));
    },
    import: async (items) => {
      const existing = new Set([...events.values()].map((e) => key(e.item)));
      for (const item of items)
        if (!existing.has(key(item)))
          await append(item, true, `import:${key(item)}`, true);
    },
    set: (item, saved, changeId) => append(item, saved, changeId, false),
  };
}
