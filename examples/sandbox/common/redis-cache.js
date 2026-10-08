// AIWAF's Node rate limiter accepts a cache implementing these list operations.
module.exports = function createRedisCache(createClient) {
  const url = process.env.AIWAF_REDIS_URL;
  if (!url) return undefined;
  const prefix = process.env.AIWAF_RATE_CACHE_KEY_PREFIX || 'sandbox:node:';
  const client = createClient({ url, socket: { connectTimeout: 2000, reconnectStrategy: false } });
  client.on('error', error => console.error('[sandbox Redis]', error.message));
  let connection;
  client.on('end', () => { connection = undefined; });
  const cache = {};
  for (const method of ['lPush', 'expire', 'lLen', 'lRange']) {
    cache[method] = async (key, ...args) => {
      if (!client.isReady) {
        connection ||= client.connect().catch(error => { connection = undefined; throw error; });
        await connection;
      }
      return client[method](prefix + key, ...args);
    };
  }
  return cache;
};
