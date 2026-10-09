const runtimeRequire = require('node:module').createRequire(require('node:path').resolve(__dirname, '../aiwaf-proxy/package.json'));
const express = runtimeRequire('express');
const { createProxyMiddleware } = require('../common/proxy');
const aiwaf = runtimeRequire('aiwaf');
const cache = require('../common/redis-cache')(runtimeRequire('redis').createClient);
const app = express();
app.use(express.json());
app.use(aiwaf.auto({ cache, WINDOW_SEC: 10, MAX_REQ: 1000, FLOOD_REQ: 2000,
  staticKeywords: ['.env', '.git', '../'], AIWAF_REQUIRED_HEADERS: [],
  AIWAF_HEADER_VALIDATION: true, AIWAF_METHOD_POLICY_ENABLED: true,
  AIWAF_ALLOWED_METHODS: ['GET', 'POST', 'HEAD', 'OPTIONS'],
  AIWAF_MIDDLEWARE_LOGGING: true,
  AIWAF_MIDDLEWARE_LOG_PATH: '/tmp/assessment-aiwaf.jsonl' }));
app.use(createProxyMiddleware({ target: process.env.TARGET_BASE_URL || 'http://security-fixture:8090', changeOrigin: true }));
app.listen(3000);
