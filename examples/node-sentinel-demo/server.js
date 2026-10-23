'use strict';

const http = require('node:http');

/**
 * Disposable Node.js app for a Liara Sentinel diagnostic demonstration.
 * No external packages, secrets, persistent state, or external HTTP calls.
 * Never enable the failure flag on production workloads.
 */
function handleRequest(req, res) {
  const path = new URL(req.url || '/', 'http://localhost').pathname;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');

  if (path !== '/' && path !== '/health') {
    res.writeHead(404);
    res.end(JSON.stringify({ ok: false, error: 'not_found' }));
    return;
  }

  const requireFlag = process.env.SENTINEL_REQUIRE_DEMO_FLAG === 'true';
  const flagIsSet = Boolean(process.env.SENTINEL_DEMO_FLAG);
  if (requireFlag && !flagIsSet) {
    // Emit nonsecret, evidence-rich app logs for controlled diagnosis.
    console.error('ConfigurationError: missing environment variable SENTINEL_DEMO_FLAG; HTTP 500 internal server error');
    res.writeHead(500);
    res.end(JSON.stringify({ ok: false, error: 'demo_configuration_missing' }));
    return;
  }

  res.writeHead(200);
  res.end(JSON.stringify({ ok: true, service: 'liara-sentinel-node-demo' }));
}

function makeServer() {
  return http.createServer(handleRequest);
}

if (require.main === module) {
  const port = Number(process.env.PORT || 8000);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    console.error('Invalid PORT');
    process.exit(1);
  }
  makeServer().listen(port, '0.0.0.0', () => {
    console.log('Sentinel Node demo listening on ' + port);
  });
}

module.exports = { makeServer };
