# 0010: A built-in `health` command for the image's HEALTHCHECK

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Accepted (2026-11-03)
Date: 2026-11-03
Authors: Stephen Cox

## Context

A `kind: service` image's HEALTHCHECK (`includes/docker/healthcheck.Dockerfile.jinja`, rendered into the
template-python-owned Dockerfile; template-container's decision 0001 leaves the Dockerfile to the stack) is
an inline `python -c` one-liner. It already asks the app over HTTP, not just whether the port is open: it
fetches `http://127.0.0.1:<port><health_path>`, taking the port from `<PREFIX>LISTEN_PORT` or the
rendered default. But:

- It reads only the environment variable. A port set in the config file (`listen.port`) is missed, so the
  container goes unhealthy while the app serves fine.
- It is a string inside a Dockerfile: untested, not linted, and the same logic is written again wherever
  something else needs "is it healthy?" (the systemd unit, a compose `healthcheck:`, an operator by hand).
- Its host is always `127.0.0.1`, so a service bound to one specific address fails it.

## Decision

- **`<project> health`** (`cli.py`, `kind: service` only): loads the config as `serve` does, fetches
  `http://<host>:<port><health_path>` with a short timeout (`--timeout`, default 4 seconds) and exits 0 on
  a 2xx answer, 1 on anything else (refused, timeout, non-2xx), 2 on a config error, like the other
  commands. `<host>` is `127.0.0.1` when `listen.host` is a wildcard (`0.0.0.0`, `::`), otherwise
  `listen.host`. One line on stderr says why it failed; nothing on success. Standard library only
  (`urllib.request`), so it adds no dependency and imports neither FastAPI nor uvicorn.
- **`--ready`** checks `/readyz` instead of `health_path` (readiness, [0006](0006-lifespan-threads.md)).
  The HEALTHCHECK keeps liveness: a dependency outage must not mark the container unhealthy.
- **The HEALTHCHECK** becomes `CMD ["/opt/venv/bin/<project>", "health"]`, same interval, timeout and
  retries. It calls the real binary, not the `puid_pgid` entrypoint shim on PATH, so a check every 30
  seconds never runs the shim's ownership fix-up.
- Tests: `health` exits 0 against a running app, 1 when nothing listens and when the endpoint answers 503,
  2 on a bad config; the rendered Dockerfile's HEALTHCHECK names `health`.
- Wiki: CLI-Reference gains `health` (generated); Deployment says what the HEALTHCHECK runs.

## Alternatives considered

- **A port-only check** (`nc -z`, or a socket connect). An app that accepts connections but is wedged
  passes. It is what the one-liner already improves on.
- **curl or wget in the image.** A package in the runtime stage of every image for one call, and still a
  URL built inside the Dockerfile from the environment, missing a port set in the config file. The slim
  base image ships neither.
- **Keep the `python -c` one-liner.** Works, but stays untested and env-only, and can't be reused outside
  the image.

## Consequences

- **template-python** changes: `cli.py`, its test, the healthcheck include and the CLI-Reference page.
- **Existing services break on update unless they add the command.** `src/**` is `_skip_if_exists`, so
  `copier update` brings the new HEALTHCHECK (the Dockerfile is template-owned) but not `health` in
  `cli.py`, and the container goes unhealthy. So the change ships as `feat!:`, and docs/migrating says to
  copy `health` from a fresh render in the same PR as the update. Services today: mitm-proxy, qbt-rules
  and trackie (sluice is `kind: cli`).
- **template-container:** its k8s probes are `httpGet` and its CI smoke test curls from the runner, so
  neither runs the HEALTHCHECK, and a service missing `health` would pass CI. Its smoke test should also
  wait for `docker inspect`'s health status to be `healthy`; that is a template-container issue, wanted
  before the existing services update. Its compose comment ("polls `<health_path>`") stays true.
- **Projects without a CLI:** a `library` has no image and no `cli.py`, so nothing changes. `kind: cli`
  gets no `health` (nothing long-running to check) and its image keeps no HEALTHCHECK.
- **Images without curl** are unaffected: the check needs only the project's own Python.
- **Staged migrations.** While the entry point is still legacy code (no Typer CLI yet), it must accept
  `health` from the first PR, as docs/migrating already says for `serve`.
- Rollback: restore the one-liner include; the command can stay.
- **Follow-up, one `feat!:` PR** after approval:
  1. `cli.py`: the `health` command with `--ready` and `--timeout`, and its tests in the rendered project.
  2. `includes/docker/healthcheck.Dockerfile.jinja`: exec form calling `/opt/venv/bin/<project> health`.
  3. Template tests: the rendered Dockerfile's HEALTHCHECK names `health`.
  4. docs/migrating: add `health` when updating an existing service, and accept it in a legacy entry point.

## Resolved questions

The brain coordinator accepted every recommended answer for Stephen on 2026-11-03.

1. **Should the HEALTHCHECK pass `--ready`?** No: it stays liveness. Docker marks the container unhealthy,
   and orchestrators that act on that restart it; restarting on a dependency outage only adds churn.
   Readiness stays the k8s readinessProbe's job.
2. **A breaking release, or a HEALTHCHECK that falls back to the one-liner when `health` is missing?**
   Breaking, with no fallback. A fallback needs a shell-form command that can't tell "no such command" from
   "unhealthy" (Typer exits 2 for both an unknown command and a config error), and three services is a
   small migration.
