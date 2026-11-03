# 0007: A Prometheus `/metrics` endpoint on interpose

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Proposed
Date: 2026-11-03
Authors: Stephen Cox

## Context

[0004](0004-fastapi-only.md) left metrics out of the skeleton until more than one service needed them.
qbt-rules serves `/metrics` today with prometheus_client in multiprocess mode under Gunicorn, and becomes a
single-process app after its port (#33); mitm-proxy and sluice already export Prometheus text through
[interpose](https://github.com/metalayerlab/interpose)'s `interpose.metrics` (its design 0002), which every
`service` already depends on ([0003](0003-interpose-config.md), pinned at v0.2.0).

## Decision

`api.py` (`kind: service`):

- `create_app` builds an `interpose.metrics.Registry`, exposed as `app.state.metrics`, with one metric:
  `<package>_build_info{version="..."} 1`, a gauge (the usual way to export a version).
- `GET /metrics` (tag `meta`) answers `registry.render()` with interpose's `CONTENT_TYPE`
  (`text/plain; version=0.0.4; charset=utf-8`). It is `async`, so rendering runs on the event loop.
- **The hook** is the registry itself: the app registers its own metrics on it in `create_app` (or code
  that receives it), `app.state.metrics.register(Counter(...))`. Label values are declared up front, as
  interpose requires, so traffic can't add series.
- **Threads.** interpose's metrics aren't locked. A metric changed from a background thread
  ([0006](0006-lifespan-threads.md)) is safe when one thread owns each series and every label set exists
  before the first scrape (creating a series resizes the dict the scrape iterates); otherwise change it on
  the event loop, or export it as a `Gauge(read=...)` computed at scrape time.
- **HTTP metrics middleware** stays the app's: one that records request counts or latency registers its
  metrics on the same registry, with the route template (not the raw path) as a declared label.
- Test: `/metrics` answers 200 with the content type, the build info line and an app-registered counter.
- Wiki: HTTP-API-Reference describes `/metrics`; Deployment's Kubernetes section (`k8s` in `contrib`) says
  to admit the scraper's namespace in the NetworkPolicy and keep `/metrics` off the public ingress route.

`contrib/k8s/networkpolicy.yaml` is template-container's, so this record changes nothing there; a commented
scraper allowance in that file is a template-container change.

## Alternatives considered

- **prometheus_client.** A new dependency next to the one every service already has, and its default
  registry is process-global, which makes tests share state. An app that needs it (for example its
  process collector) replaces the route.
- **A metrics port separate from the API.** Keeps `/metrics` off the ingress by construction, but adds a
  second listener, a question and manifest changes for every service; the ingress route and the
  NetworkPolicy can do the same job.
- **No default metric.** An empty registry renders an empty body, which a scraper accepts but shows
  nothing; build info costs one line and answers "which version is running".

## Consequences

- Every new service exposes `/metrics` on its API port, unauthenticated, like the health endpoints. A
  public ingress that routes `/` exposes it too unless the route excludes it.
- `docs/openapi.json` ([0005](0005-openapi-snapshot.md)) gains the `/metrics` path.
- Existing services (their `src/` is their own) copy the route from a fresh render; docs/migrating says how
  to move prometheus_client metrics across.

## Open questions

- Should template-container's NetworkPolicy carry a commented allowance for a `monitoring` namespace on
  the `http` port? Recommendation: yes, commented out like its `extra_ports` block, since the scraper's
  namespace differs per cluster. That's an issue for template-container.
