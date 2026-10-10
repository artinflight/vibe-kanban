import assert from 'node:assert/strict';
import http from 'node:http';
import net from 'node:net';
import { once } from 'node:events';
import { createHistoryProxy } from './chat-history-proxy.mjs';

const uuid = 'a310e7af-f663-4267-84e9-96b9a6b17048';
const path = `/api/execution-processes/${uuid}/log-history`;
const seen = [];
function upstream(name) {
  const server = http.createServer(async (req, res) => {
    let body = '';
    for await (const chunk of req) body += chunk;
    seen.push({ name, method: req.method, path: req.url, body });
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ name, body }));
  });
  server.on('upgrade', (_, socket) => {
    socket.end(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: test\r\nConnection: Upgrade\r\n\r\n${name}`);
  });
  server.listen(0, '127.0.0.1');
  return server;
}
const primary = upstream('primary');
const reader = upstream('reader');
await Promise.all([once(primary, 'listening'), once(reader, 'listening')]);
let ready = true;
const proxy = createHistoryProxy({ primaryPort: primary.address().port,
  readerPort: reader.address().port, prepare: async () => ready });
proxy.listen(0, '127.0.0.1');
await once(proxy, 'listening');
const base = `http://127.0.0.1:${proxy.address().port}`;
try {
  assert.equal((await (await fetch(base + path + '?limit=3&before=9')).json()).name, 'reader');
  assert.equal(seen.at(-1).path, path + '?limit=3&before=9');
  for (const method of ['POST', 'PUT', 'DELETE', 'PATCH']) {
    const result = await (await fetch(base + path, { method, body: 'keep queued text' })).json();
    assert.deepEqual(result, { name: 'primary', body: 'keep queued text' });
  }
  for (const suffix of ['/extra', '/', '%2f', '/%2e%2e/info'])
    assert.equal((await (await fetch(base + path + suffix)).json()).name, 'primary');
  ready = false;
  assert.equal((await (await fetch(base + path)).json()).name, 'primary');
  const socket = net.connect(proxy.address().port, '127.0.0.1');
  await once(socket, 'connect');
  socket.write(`GET ${path} HTTP/1.1\r\nHost: test\r\nConnection: Upgrade\r\nUpgrade: test\r\n\r\n`);
  let response = '';
  for await (const chunk of socket) response += chunk;
  assert(response.endsWith('primary'));
  console.log('Passed selective GET, query, fallback, write-body and WebSocket routing checks');
} finally {
  for (const server of [proxy, primary, reader]) server.close();
}
