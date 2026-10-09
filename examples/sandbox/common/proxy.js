const { createRequire } = require('node:module');
const { resolve } = require('node:path');
const { Readable } = require('node:stream');
const runtimeRequire = createRequire(resolve(process.cwd(), 'package.json'));
const { createProxyServer } = runtimeRequire('httpxy');

// Literal catch-all proxying needs no glob matcher or vulnerable pattern dependencies.
function createProxyMiddleware(options) {
  const proxy = createProxyServer({ target: options.target, changeOrigin: options.changeOrigin !== false });
  return (req, res, next) => new Promise(resolve => {
    res.once('finish', resolve);
    res.once('close', resolve);
    let bytes = req.aiwafRawBody;
    if (!bytes && req.body !== undefined && req.readableEnded) {
      const type = String(req.headers['content-type'] || '');
      bytes = Buffer.isBuffer(req.body) ? req.body : Buffer.from(type.includes('application/x-www-form-urlencoded')
        ? new URLSearchParams(req.body).toString() : JSON.stringify(req.body));
    }
    const forward = {};
    if (bytes) {
      req.headers['content-length'] = String(bytes.length);
      delete req.headers['transfer-encoding'];
      forward.buffer = Readable.from([bytes]);
    }
    proxy.web(req, res, forward).catch(error => {
      if (!res.headersSent) { res.statusCode = 502; res.end('bad_gateway'); }
      else res.destroy(error);
      resolve();
    });
  });
}

module.exports = { createProxyMiddleware };
