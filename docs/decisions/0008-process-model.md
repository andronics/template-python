# 0008: One uvicorn process per pod; scale by replicas

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Proposed
Date: 2026-11-03
Authors: Stephen Cox

## Context

The skeleton already runs one process: `serve` calls `uvicorn.run(app)` without `workers`, and
template-container's Deployment has `replicas: 1` and `strategy: Recreate`. Nothing says why, or how to
scale. The services moving over ran Gunicorn with several workers: qbt-rules has a `server.workers` setting,
a `post_fork` hook to restart its worker thread in each child, prometheus_client's multiprocess mode, and a
scheduler that must run exactly once (#34). [0006](0006-lifespan-threads.md) puts background threads in the
lifespan and [0007](0007-metrics-endpoint.md) gives each process an in-memory metrics registry; both assume
one process.

## Decision

Documentation only; no code or manifest changes.

- **One uvicorn process per pod (or per systemd unit).** No `--workers`, no Gunicorn. Concurrency comes from
  the event loop and FastAPI's thread pool for `def` endpoints.
- **Scale by replicas.** More throughput is more pods, each one process, each scraped as its own target.
- **A lifespan scheduler runs once per process**, so a service with one keeps `replicas: 1` (with `Recreate`,
  so an update never overlaps two), or moves the scheduler to its own singleton Deployment (`replicas: 1`,
  the same image, a scheduler subcommand as `args`) and scales the API separately.
- **Leader election stays in the app**, if one ever needs several schedulers with one active. The template
  ships none.
- **A port from Gunicorn** drops its `workers` setting; if the setting must stay readable for a release, a
  value above 1 is a configuration error that says to scale by replicas.

Where it's written: the wiki's Deployment page gets a "Process model" section for `kind: service`, and the
page now renders for every service, not only those with `contrib` (a service without manifests still needs
to know how to scale). docs/migrating's "Server" bullet points here. The wiki standard doesn't require the
new heading, so existing services' pages (theirs once written) stay valid.

## Alternatives considered

- **A `workers` setting passed to uvicorn.** Multiplies every per-process thing: background threads and
  schedulers run once per worker, and `/metrics` answers for whichever worker took the request, so it needs
  a multiprocess registry. Kubernetes already does process supervision and load balancing.
- **Gunicorn with uvicorn workers.** The same problems, plus a second server to configure ([0004](0004-fastapi-only.md)).
- **Leader election in the template.** A Lease client and RBAC for every service, for a need none has yet.

## Consequences

- Services without `contrib` gain a Deployment page (process model and upgrading), linked from Home and the
  sidebar. New projects only: existing services all have `contrib`, and the page is theirs once written.
- A service that scales past one replica must first move its scheduler out, or make its jobs idempotent.
- qbt-rules' `post_fork` hook and multiprocess metrics have no equivalent and are dropped in its port.

## Open questions

None.
