// Transport boundary only: the real WebSocket patch hook and approval selector
// run in the mounted composer fixture. No live socket or backend is opened.
export const sockets: FixtureSocket[] = [];
class FixtureSocket {
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  open() {
    this.onopen?.();
  }
  message(value: unknown) {
    this.onmessage?.({ data: JSON.stringify(value) });
  }
  close() {
    this.onclose?.();
  }
}
export async function openLocalApiWebSocket() {
  const socket = new FixtureSocket();
  sockets.push(socket);
  return socket;
}
export function publish(pending: Record<string, unknown>, ready = true) {
  const socket = sockets.at(-1)!;
  socket.message({
    JsonPatch: [{ op: 'replace', path: '/pending', value: pending }],
  });
  if (ready) socket.message({ Ready: true });
}
