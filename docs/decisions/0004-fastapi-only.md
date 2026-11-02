# 0004: FastAPI is the only web framework for `kind: service`

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Accepted (2026-11-02)
Date: 2026-11-02
Authors: Stephen Cox

## Context

`kind: service` renders a FastAPI app (`src/<pkg>/api.py`), served by uvicorn from the CLI's `serve`
command, which the Dockerfile (`CMD ["serve"]`), the systemd unit and template-container's compose and k8s
manifests all run. The services still to migrate use other frameworks: trackie and qbt-rules are Flask on
gunicorn, ferryman is Starlette on uvicorn. A `framework` question (fastapi | flask | starlette | none) was
considered so they could migrate as they are.

## Decision

No `framework` question. FastAPI on uvicorn is the one web stack for `kind: service`, and the skeleton stays
as it is. A service that uses another framework is ported to FastAPI as part of its template migration.

Why:

- **OpenAPI contracts between services.** Every service publishes a typed schema (`/openapi.json`, the
  wiki's generated endpoint table), so services and their clients interoperate against a contract.
- **Async, I/O-bound workloads.** These services mostly wait on other services and files; FastAPI is async
  first and still runs plain `def` endpoints in a thread pool, so a port can keep synchronous code.
- **Typed APIs under strict mypy.** Request and response models are Pydantic types the checker sees.
- **One server everywhere.** uvicorn behind `serve`, the same in the image, k8s and systemd: no per-framework
  server commands, health wiring or manifest variants.

## Alternatives considered

- **A `framework` question.** Four app modules, test suites, wiki generators and server commands to keep
  green, for frameworks we are leaving. Flask is synchronous and publishes no contract; plain Starlette
  means rebuilding what FastAPI adds on top of it (validation, OpenAPI); `none` leaves the manifests'
  `serve` unimplemented.
- **Litestar.** Comparable features, smaller ecosystem.

## Consequences

Nothing changes for existing projects: mitm-proxy is already FastAPI, and sluice and interpose are not
services. trackie, qbt-rules and ferryman are ported to FastAPI during their migrations
([docs/migrating/README.md](../migrating/README.md), "Porting a service to FastAPI"). The skeleton has no
HTML templates, static files, sessions, background workers, metrics or multi-worker serving: a port that needs
one adds it in the project, and whichever is needed by more than one service becomes a template change with
its own record.
