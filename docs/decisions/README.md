# Design records

Why template-python is the way it is. Copy [0000-template.md](0000-template.md) to `NNNN-short-title.md` and
add a line below. **Read this index first.** The split itself is template-base's decision 0001.

| # | Title | Status | Decision in one line |
|---|---|---|---|
| [0001](0001-python-overlay.md) | The python stack overlay | Proposed | A Python project is base + this overlay (+ template-container for an image): project-template's Python questions unchanged, cheap checks in `checks.d/20-python.sh`, the rest in `stack-ci.yml`, `base_answers` for updates; rebuilds project-template's 0005, 0012 and 0017 |
| [0002](0002-tag-check-workflow.md) | A tag-check workflow for git-tag-pinned dependencies | Accepted (2026-11-02) | A template-owned weekly `python-tag-check.yml` finds GitHub tag pins in pyproject.toml and opens one `chore(deps)` PR per dependency (pin rewrite + `uv lock --upgrade-package`), with the release App if set; in every project, a no-op without such pins |
| [0003](0003-interpose-config.md) | A thin `config.py` on interpose | Accepted (2026-11-02) | `service` and `cli` projects depend on interpose by git tag (no question); `config.py` stays project-owned and holds only SETTINGS, Config and cross-setting rules; replaces project-template's 0020 |
| [0004](0004-fastapi-only.md) | FastAPI is the only web framework for `kind: service` | Accepted (2026-11-02) | No `framework` question: every service is FastAPI on uvicorn behind `serve`; Flask and Starlette services are ported during their migration |
