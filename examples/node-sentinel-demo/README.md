# Node.js disposable example for Liara Sentinel

Zero-dependency Node.js server compatible with the Liara Node platform.
Node package start script launches server.js using built-in node:http.
Listens on process.env.PORT or port 8000 on host 0.0.0.0.

GET / and GET /health return JSON, HTTP 200 when healthy.
Set SENTINEL_REQUIRE_DEMO_FLAG=true and leave SENTINEL_DEMO_FLAG unset to produce
real HTTP 500 responses and a non-secret ConfigurationError log.
Set SENTINEL_DEMO_FLAG=ready to recover after updating Liara env settings.

Do not use on production services. This is an operator-reviewed demo fixture.

On Windows Sentinel choose existing-app API, path node-sentinel-demo,
platform node, port 8000, and an explicitly allowed disposable Node app.
The endpoint returns SUBMITTED only; confirm releases and independent HTTP health.
See docs/18-operator-steps-fa.md in the parent repo for the detailed walkthrough.
