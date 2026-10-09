// Run inside the Express image as a separate process; shared Redis stays up.
const { createRequire } = require('node:module');
const load = createRequire('/workspace/examples/sandbox/aiwaf-proxy/package.json');
const express = load('express');
const { createClient } = load('redis');
const aiwaf = load('aiwaf');
const { createProxyMiddleware } = require('/workspace/examples/sandbox/common/proxy');

async function request(app) {
  const server = await new Promise(resolve => {
    const value = app.listen(0, '127.0.0.1', () => resolve(value));
  });
  try {
    const response = await fetch(`http://127.0.0.1:${server.address().port}/protected`, {
      headers: { 'X-Forwarded-For': '93.19.27.41', 'User-Agent': 'Mozilla/5.0 Chrome/130.0.0.0 Safari/537.36',
                 'Accept': 'application/json,text/html;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9' },
      signal: AbortSignal.timeout(10000)
    });
    return { status: response.status, body: await response.text() };
  } finally {
    await new Promise(resolve => server.close(resolve));
  }
}

async function main() {
  const client = createClient({ url: 'redis://127.0.0.1:1', socket: { reconnectStrategy: false, connectTimeout: 1000 } });
  client.on('error', () => {});
  let unavailable = false;
  try { await client.connect(); } catch (_) { unavailable = true; }
  const cache = Object.fromEntries(['lPush', 'expire', 'lLen', 'lRange'].map(name => [name, (...args) => client[name](...args)]));
  const app = express();
  let calls = 0;
  app.use(aiwaf({ cache, AIWAF_MIDDLEWARES: ['rate_limit'], AIWAF_MIDDLEWARE_LOGGING: false }));
  app.get('/protected', (_req, res) => { calls++; res.json({ unexpected: true }); });
  const redis = await request(app);
  const upstreamApp = express();
  upstreamApp.use(createProxyMiddleware({ target: 'http://127.0.0.1:1' }));
  const upstream = await request(upstreamApp);
  const checks = [
    { category: 'A10', check: 'redis_outage_rejects_request', scope: 'local JavaScript Express SDK, separate process',
      status: unavailable && redis.status === 503 && redis.body.includes('temporarily_unavailable') && calls === 0
        && !/ECONN|127\.0\.0|stack|redis:\/\//.test(redis.body) ? 'pass' : 'fail',
      evidence: { actual_connection_failure: unavailable, status: redis.status, application_calls: calls } },
    { category: 'A10', check: 'upstream_outage_generic_response', scope: 'shared JavaScript proxy helper, separate process',
      status: upstream.status === 502 && upstream.body === 'bad_gateway' ? 'pass' : 'fail',
      evidence: { status: upstream.status, generic_response: upstream.body === 'bad_gateway' } }
  ];
  console.log(JSON.stringify({ checks }));
  process.exit(checks.every(row => row.status === 'pass') ? 0 : 1);
}
main().catch(() => { console.error('Isolated outage assessment failed'); process.exit(1); });
