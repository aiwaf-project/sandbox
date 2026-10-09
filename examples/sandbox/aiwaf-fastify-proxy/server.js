const fastify = require('fastify')({ logger: true, bodyLimit: 65536 });
const aiwaf = require('aiwaf');
const redisCache = require('../common/redis-cache')(require('redis').createClient);
const { createProxyMiddleware } = require('../common/proxy');

const PORT = process.env.PORT || 3002;
const TARGET_BASE_URL = process.env.TARGET_BASE_URL || 'http://localhost:3001';

fastify.register(aiwaf.fastify, {
  middlewares: ['auto'],
  cache: redisCache,
  staticKeywords: ['.php', '.env', '.git', '../'],
  dynamicTopN: 5,
  WINDOW_SEC: 10,
  MAX_REQ: 25,
  FLOOD_REQ: 50,
  HONEYPOT_FIELD: 'hp_field',
  AIWAF_METHOD_POLICY_ENABLED: true,
  AIWAF_ALLOWED_METHODS: ['GET', 'POST', 'HEAD', 'OPTIONS'],
  AIWAF_HEADER_VALIDATION: true,
  AIWAF_REQUIRED_HEADERS: [],
  AIWAF_MIDDLEWARE_LOGGING: true,
  AIWAF_MIDDLEWARE_LOG_PATH: process.env.AIWAF_MIDDLEWARE_LOG_PATH || 'logs/aiwaf-requests.jsonl'
});

fastify.addHook('onRequest', async (request, reply) => {
  fastify.log.info(`[sandbox-fastify] ${request.method} ${request.url}`);
});

const proxy = createProxyMiddleware({ target: TARGET_BASE_URL, changeOrigin: true });
for (const url of ['/', '/*']) {
  fastify.route({ method: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'], url,
    handler: async (request, reply) => {
      // Native parsing and AIWAF's preValidation hook run before forwarding.
      request.raw.body = request.body;
      reply.hijack();
      await proxy(request.raw, reply.raw);
    } });
}

fastify.listen({ port: PORT, host: '0.0.0.0' }).then(() => {
  fastify.log.info(`AIWAF Fastify sandbox proxy running on port ${PORT}`);
  fastify.log.info(`Forwarding traffic to ${TARGET_BASE_URL}`);
});
