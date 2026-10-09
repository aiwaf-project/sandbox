const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { createProxyMiddleware } = require('./proxy');

async function listen(server, t) {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => { server.closeAllConnections(); server.close(); });
  return `http://127.0.0.1:${server.address().port}`;
}

test('forwards the original bytes after a body parser consumes the request', async t => {
  const upstream = await listen(http.createServer((req, res) => {
    const chunks = [];
    req.on('data', chunk => chunks.push(chunk));
    req.on('end', () => res.end(Buffer.concat(chunks)));
  }), t);
  const proxy = createProxyMiddleware({ target: upstream });
  const url = await listen(http.createServer((req, res) => {
    const chunks = [];
    req.on('data', chunk => chunks.push(chunk));
    req.on('end', () => {
      req.aiwafRawBody = Buffer.concat(chunks);
      req.body = JSON.parse(req.aiwafRawBody);
      proxy(req, res);
    });
  }), t);
  const original = '{ "email": "ordinary@example.invalid", "n": 1 }';
  const response = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: original });
  assert.equal(response.status, 200);
  assert.equal(await response.text(), original);
});

test('upstream failure sends one generic 502 without invoking another response handler', async t => {
  const stopped = http.createServer();
  await new Promise(resolve => stopped.listen(0, '127.0.0.1', resolve));
  const target = `http://127.0.0.1:${stopped.address().port}`;
  await new Promise(resolve => stopped.close(resolve));
  let nextCalls = 0;
  const proxy = createProxyMiddleware({ target });
  const url = await listen(http.createServer((req, res) => proxy(req, res, () => nextCalls++)), t);
  const response = await fetch(url);
  assert.equal(response.status, 502);
  assert.equal(await response.text(), 'bad_gateway');
  assert.equal(nextCalls, 0);
});
