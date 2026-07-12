import { afterEach, describe, expect, it, vi } from 'vitest';
import { setLocalApiTransport } from './localApiTransport';
import { streamJsonPatchEntries } from './streamJsonPatchEntries';

type Listener = (event?: unknown) => void;

class MockWebSocket {
  private listeners = new Map<string, Set<Listener>>();

  addEventListener(type: string, listener: Listener) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)!.add(listener);
  }

  close() {
    this.emit('close');
  }

  open() {
    this.emit('open');
  }

  message(data: unknown) {
    this.emit('message', { data: JSON.stringify(data) });
  }

  serverClose() {
    this.emit('close');
  }

  private emit(type: string, event?: unknown) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }
}

describe('streamJsonPatchEntries', () => {
  afterEach(() => {
    setLocalApiTransport(null);
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('keeps the last snapshot visible while a reconnect replay catches up', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'requestAnimationFrame',
      (callback: FrameRequestCallback): number => {
        callback(0);
        return 1;
      }
    );
    vi.stubGlobal('cancelAnimationFrame', () => undefined);

    const sockets: MockWebSocket[] = [];
    setLocalApiTransport({
      request: () => {
        throw new Error('unexpected request');
      },
      openWebSocket: () => {
        const socket = new MockWebSocket();
        sockets.push(socket);
        return socket as unknown as WebSocket;
      },
    });

    const snapshots: string[][] = [];
    const controller = streamJsonPatchEntries<{ content: string }>('/ws', {
      onEntries: (entries) => {
        snapshots.push(entries.map((entry) => entry.content));
      },
    });

    sockets[0]!.open();
    sockets[0]!.message({
      JsonPatch: [
        {
          op: 'add',
          path: '/entries/0',
          value: { content: 'oldest' },
        },
        {
          op: 'add',
          path: '/entries/1',
          value: { content: 'newest' },
        },
      ],
    });

    sockets[0]!.serverClose();
    await vi.advanceTimersByTimeAsync(1000);

    sockets[1]!.open();
    sockets[1]!.message({
      JsonPatch: [
        {
          op: 'add',
          path: '/entries/0',
          value: { content: 'oldest replayed' },
        },
      ],
    });

    expect(snapshots).toEqual([
      ['oldest', 'newest'],
      ['oldest replayed', 'newest'],
    ]);

    controller.close();
  });
});
