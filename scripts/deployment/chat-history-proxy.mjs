// Keep execution ownership on the primary; divert only finite history GETs.
import http from 'node:http';
import net from 'node:net';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { pathToFileURL } from 'node:url';

const run = promisify(execFile);
const historyPath = /^\/api\/execution-processes\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\/log-history$/;

export function createHistoryProxy({ primaryPort, readerPort, prepare }) {
  const server = http.createServer(async (req, res) => {
    let port = primaryPort;
    const match = historyPath.exec(req.url.split('?')[0]);
    if (req.method === 'GET' && match) {
      try {
        if (await prepare(match[1])) port = readerPort;
      } catch {
        // Never replace a primary response with fabricated or stale history.
        port = primaryPort;
      }
    }
    if (req.aborted || res.destroyed) return;
    const upstream = http.request({
      hostname: '127.0.0.1', port, method: req.method,
      path: req.url, headers: req.headers,
    }, reply => {
      res.writeHead(reply.statusCode, reply.headers);
      reply.pipe(res);
    });
    upstream.on('error', () => {
      if (!res.headersSent) res.writeHead(502);
      res.end();
    });
    req.on('aborted', () => upstream.destroy());
    res.on('close', () => {
      if (!res.writableFinished) upstream.destroy();
    });
    req.pipe(upstream);
  });
  server.on('upgrade', (req, socket, head) => {
    const upstream = net.connect(primaryPort, '127.0.0.1', () => {
      upstream.write(`${req.method} ${req.url} HTTP/${req.httpVersion}\r\n`);
      for (let i = 0; i < req.rawHeaders.length; i += 2)
        upstream.write(`${req.rawHeaders[i]}: ${req.rawHeaders[i + 1]}\r\n`);
      upstream.write('\r\n');
      if (head.length) upstream.write(head);
      upstream.pipe(socket);
      socket.pipe(upstream);
    });
    upstream.on('error', () => socket.destroy());
    socket.on('error', () => upstream.destroy());
    socket.on('close', () => upstream.destroy());
  });
  return server;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const { VK_HISTORY_BINDINGS, VK_HISTORY_SYNC, VK_PRIMARY_DATABASE } = process.env;
  if (!VK_HISTORY_BINDINGS || !VK_HISTORY_SYNC || !VK_PRIMARY_DATABASE)
    throw new Error('Explicit reader bindings, metadata synchronizer and primary DB required');
  const { readFile } = await import('node:fs/promises');
  const bindings = JSON.parse(await readFile(VK_HISTORY_BINDINGS, 'utf8'));
  const server = createHistoryProxy({
    primaryPort: bindings.primary_port,
    readerPort: bindings.reader_port,
    prepare: async id => {
      const result = await run('/usr/bin/python3', [VK_HISTORY_SYNC,
        VK_PRIMARY_DATABASE, bindings.database_copy, bindings.root, id],
      { timeout: 5000, maxBuffer: 1024 });
      return result.stdout.trim() === 'ready';
    },
  });
  server.listen(bindings.proxy_port, '127.0.0.1');
}
