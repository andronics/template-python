# Design records

Why template-python is the way it is. Copy [0000-template.md](0000-template.md) to `NNNN-short-title.md` and
add a line below. **Read this index first.** The split itself is template-base's decision 0001.

| # | Title | Status | Decision in one line |
|---|---|---|---|
| [0001](0001-python-overlay.md) | The python stack overlay | Proposed | A Python project is base + this overlay (+ template-container for an image): project-template's Python questions unchanged, cheap checks in `checks.d/20-python.sh`, the rest in `stack-ci.yml`, `base_answers` for updates; rebuilds project-template's 0005, 0012 and 0017 |
| [0002](0002-tag-check-workflow.md) | A tag-check workflow for git-tag-pinned dependencies | Accepted (2026-11-02) | A template-owned weekly `python-tag-check.yml` finds GitHub tag pins in pyproject.toml and opens one `chore(deps)` PR per dependency (pin rewrite + `uv lock --upgrade-package`), with the release App if set; in every project, a no-op without such pins |
| [0003](0003-interpose-config.md) | A thin `config.py` on interpose | Accepted (2026-11-02) | `service` and `cli` projects depend on interpose by git tag (no question); `config.py` stays project-owned and holds only SETTINGS, Config and cross-setting rules; replaces project-template's 0020 |
| [0004](0004-fastapi-only.md) | FastAPI is the only web framework for `kind: service` | Accepted (2026-11-02) | No `framework` question: every service is FastAPI on uvicorn behind `serve`; Flask and Starlette services are ported during their migration |
| [0005](0005-openapi-snapshot.md) | Commit the OpenAPI schema and check it in CI | Proposed | `kind: service` commits `docs/openapi.json` (info.version fixed), written and checked by `gen-wiki.py` wherever it already runs; a PR-only oasdiff job fails a breaking change the PR doesn't declare (`feat!:`) |
| [0006](0006-lifespan-threads.md) | Background threads in the skeleton's lifespan | Proposed | `api.py` gets `BackgroundThreads` (`add(name, target(stop))`, started and joined by a FastAPI `lifespan`); `/readyz` answers 503 naming a dead thread; liveness unchanged |
| [0007](0007-metrics-endpoint.md) | A Prometheus `/metrics` endpoint on interpose | Proposed | `api.py` serves an `interpose.metrics.Registry` (`app.state.metrics`, with `<package>_build_info`) at `/metrics`; apps register their own metrics on it; the NetworkPolicy allowance is template-container's |
| [0008](0008-process-model.md) | One uvicorn process per pod; scale by replicas | Proposed | Documented, not changed: no `--workers`, scale by replicas, a lifespan scheduler needs `replicas: 1` or its own singleton Deployment, leader election stays in the app; the Deployment wiki page renders for every service |
| [0009](0009-service-workdir.md) | A service's working directory is its state directory | Proposed | `kind: service` images get `WORKDIR /var/lib/<project>` and the systemd unit `WorkingDirectory=` the same, so relative paths never resolve in `/` (where an old `/config` volume could be read); `cli` images unchanged |
