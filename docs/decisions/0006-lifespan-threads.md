# 0006: Background threads in the skeleton's lifespan

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Proposed
Date: 2026-11-03
Authors: Stephen Cox

## Context

[0004](0004-fastapi-only.md) left background workers out of the skeleton, to be added as a template change
once more than one service needed them. qbt-rules runs a worker thread and a croniter scheduler thread beside
its API, and docs/migrating tells every port to move such threads into a `lifespan`; without a stub, each
port invents its own start, stop and health wiring (#32). The migrating docs already say threads start in a FastAPI `lifespan` and `/readyz` answers 503
when one dies, but the skeleton had no lifespan to point at.

## Decision

`api.py` (`kind: service`) gets:

- **`BackgroundThreads`**, a small registry. `add(name, target)` registers a thread; `target(stop)` runs until
  the `threading.Event` it is given is set (`while not stop.wait(interval): ...`). Names are unique.
  `start()` creates and starts a daemon thread per target; `shutdown()` sets `stop` and joins each for up to
  `join_timeout` seconds (default 5); `dead()` names the registered threads not running.
- **A `lifespan`** in `create_app` that starts them and shuts them down. Threads are registered in
  `create_app`, never at import, and the registry is `app.state.threads`.
- **`/readyz` answers 503** with `{"detail": "background thread not running: <names>"}` when one has
  returned or raised, and documents the 503 in the OpenAPI schema. `health_path` stays dependency-free, so
  an orchestrator stops routing to the pod but doesn't restart it for this alone.
- Unit tests: a thread starts and is stopped with the lifespan; a thread that exits makes `/readyz` 503 while
  liveness stays 200; a duplicate name is refused.

With no thread registered, the skeleton behaves as before.

## Alternatives considered

- **asyncio tasks instead of threads.** The services moving over run synchronous code (requests, sqlite,
  croniter loops); a thread runs it unchanged. An app that wants a task can start one in the same lifespan.
- **Restarting a dead thread.** Hides the bug that killed it; readiness failing makes it visible and a
  deployment can restart the pod. An app that wants a supervisor writes one into its target.
- **Failing liveness on a dead thread.** The pod restarts, which may be what an app wants, but it couples
  liveness to app code, which the skeleton keeps dependency-free. An app can add it to its own liveness.
- **A separate module or library.** About forty lines; in `api.py` it's visible where routes and lifespan
  meet. If several services grow the same extras, it can move to interpose.

## Consequences

- New services get the pattern; existing ones (their `src/` is their own) copy it from a fresh render.
- Shutdown blocks for at most `join_timeout` per thread; a target must check `stop` at least that often.
  Daemon threads that miss it don't hold up the exit.
- A lifespan scheduler runs once per process: with more than one replica it runs more than once (see the
  process-model record).
- Worker and scheduler subcommands, and extra Deployments, stay in the app.
- Wiki: HTTP-API-Reference says what makes `/readyz` 503 (new projects). docs/migrating points at the stub.

## Open questions

None.
