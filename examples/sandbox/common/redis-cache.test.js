const { test } = require('node:test');
const assert = require('node:assert/strict');
const createCache = require('./redis-cache');

test('Redis rate cache shares its connection and prefixes every list operation', async () => {
  const original = { url: process.env.AIWAF_REDIS_URL, prefix: process.env.AIWAF_RATE_CACHE_KEY_PREFIX };
  process.env.AIWAF_REDIS_URL = 'redis://redis:6379/3';
  process.env.AIWAF_RATE_CACHE_KEY_PREFIX = 'sandbox:test:';
  const calls = [];
  const handlers = {};
  let connections = 0;
  const client = {
    isReady: false,
    on(event, handler) { handlers[event] = handler; },
    async connect() { connections++; await Promise.resolve(); this.isReady = true; },
  };
  for (const method of ['lPush', 'expire', 'lLen', 'lRange']) {
    client[method] = async (...args) => { calls.push([method, ...args]); return 1; };
  }
  try {
    const cache = createCache(options => {
      assert.equal(options.url, 'redis://redis:6379/3');
      return client;
    });
    await Promise.all([cache.lPush('ratelimit:ip', '123'), cache.lLen('ratelimit:ip')]);
    await cache.expire('ratelimit:ip', 20);
    await cache.lRange('ratelimit:ip', 0, -1);
    assert.equal(connections, 1);
    assert.ok(calls.every(call => call[1] === 'sandbox:test:ratelimit:ip'));
    assert.deepEqual(calls[2], ['expire', 'sandbox:test:ratelimit:ip', 20]);
    assert.deepEqual(calls[3], ['lRange', 'sandbox:test:ratelimit:ip', 0, -1]);
    client.isReady = false;
    handlers.end();
    await cache.lLen('ratelimit:ip');
    assert.equal(connections, 2);
  } finally {
    for (const [key, value] of [['AIWAF_REDIS_URL', original.url], ['AIWAF_RATE_CACHE_KEY_PREFIX', original.prefix]]) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
  }
});
