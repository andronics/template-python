# Migrating existing projects

One prompt per project, run in that project's own Claude Code session. Each one replaces `.copier-answers.yml`
with the stacked templates' answers files in one reviewed PR, after a 3-way merge of every template file
(the old template's version → the new templates', onto the project's).

| Project | From | Prompt |
|---|---|---|
| metalayerlab/interpose | project-template v0.1.18, library | [interpose.md](interpose.md) |
| metalayerlab/sluice | project-template v0.1.15, cli + image | [sluice.md](sluice.md) |
| metalayerlab/mitm-proxy | project-template v0.1.17, service + image | [mitm-proxy.md](mitm-proxy.md) |

They use template-base `v2.0.2`, template-python `v2.0.0` and template-container `v2.0.0`, the first releases of the overlays.

A project that was never made from a template has no old render to merge against: follow
[no-template-history.md](no-template-history.md) (a 2-way merge; first used for andronics/trackie). Its
section 7 covers a staged migration, where the old code keeps running for a few PRs.

## After a template update

Changes a template update can't make, because the files are the project's (`src/`, `tests/`):

| Change | For | Prompt |
|---|---|---|
| `config.py` on interpose's settings engine (decision [0003](../decisions/0003-interpose-config.md)) | `service` and `cli` projects made before it | [interpose-config.md](interpose-config.md) |

## Porting a service to FastAPI

`kind: service` is FastAPI on uvicorn only (decision [0004](../decisions/0004-fastapi-only.md)). A Flask or
Starlette service (trackie, qbt-rules, ferryman) is ported in its migration PR, after the templates are
applied, so the skeleton's `api.py`, `cli.py serve`, `tests/unit/test_api.py` and wiki are the starting point:

- **Routes** move into `create_app(config)` in `api.py`, each with a `summary` (the wiki's endpoint table is
  generated from the OpenAPI schema). Request bodies and responses become Pydantic models; plain `def`
  endpoints keep synchronous code (requests, sqlite) working in FastAPI's thread pool.
- **Health:** `health_path` stays dependency-free; `/readyz` answers 503 while a dependency is down (the k8s
  readiness probe reads it). Keep any old health path as an extra route until its callers move.
- **Server:** `serve` runs uvicorn with the app object. Drop gunicorn, its config and any `gunicorn ... app:app`
  command; the Dockerfile, systemd unit and contrib manifests already run `<project> serve`. One process per
  pod: scale by replicas, never `--workers` (decision [0008](../decisions/0008-process-model.md), the wiki's
  Deployment page). A `workers` setting the old config had goes; if it must stay readable for a release, a
  value above 1 is a `ConfigError` that says to scale by replicas.
- **Background threads** (pollers, workers, schedulers) start and stop in the skeleton's FastAPI `lifespan`,
  not at import or app creation: register each in `create_app` with `threads.add("worker", run)`, where
  `run(stop)` loops until the `threading.Event` it gets is set (`BackgroundThreads` in `api.py`, decision
  [0006](../decisions/0006-lifespan-threads.md)). The lifespan starts them, and on shutdown sets `stop` and
  joins each with a timeout; `/readyz` answers 503 naming any that died. Tests that build the app without
  `with TestClient(app)` never start them.
- **Metrics:** the skeleton serves `/metrics` from an interpose `Registry` (`app.state.metrics`, decision
  [0007](../decisions/0007-metrics-endpoint.md)). Re-declare prometheus_client metrics as interpose
  `Counter`, `Gauge` and `Histogram` on it, keeping their names, and drop prometheus_client's multiprocess
  mode (one process per pod). Label values are declared up front (`Label("status", [...])`).
- **Errors** are `{"detail": "..."}` (`HTTPException`); keep the old shape only if a client depends on it,
  and say so in a design record.
- **Tests:** Flask's `test_client()` / pytest-flask become `fastapi.testclient.TestClient`. Keep each old
  route's test, pointed at the new app, so the port shows nothing a client sees changed. Until then, the
  Flask tests run under the template's `filterwarnings = ["error"]`: a response that holds a file or a
  stream (`send_file`, a generator) and is never closed warns when it is collected, and that fails the test.
  Close each one: `with client.get("/x") as r:`, or `r.close()`.

