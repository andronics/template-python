# template-python

The stack overlay for a **Python** project (uv, ruff, mypy strict, pytest with an 80% floor, Typer, FastAPI).
It goes on top of [template-base](https://github.com/andronics/template-base):

```sh
uvx copier copy --trust gh:andronics/template-base my-project
uvx copier copy --trust gh:andronics/template-python my-project
uvx copier copy --trust gh:andronics/template-container my-project   # with container_image: the image's workflows, docker/k8s manifests
```

It asks `kind` (`service`, `cli`, `library`, `stdlib-cli`) and the Python questions, and reads the project's identity from
base's answers. It needs template-base `v2.0.0` or later.

## What it adds

| Path | What |
|---|---|
| `pyproject.toml`, `src/<package>/`, `tests/` | The package skeleton: config on [interpose](https://github.com/metalayerlab/interpose)'s settings engine (`<PREFIX>_<KEY>_FILE` > env > file > default; decision 0003), CLI, HTTP API; unit and opt-in integration tests. `stdlib-cli`: one standard-library-only program file that runs as `python3 -IS`, argparse, no config engine, checked by `scripts/check-stdlib.py` (decision 0011). `src/` and `tests/` are the project's once written |
| Slots | `.agents/stack.md`, `stack-ci.yml` (tests, integration, Markdown lint, manifests), `.gitignore`, `.pre-commit-config.yaml`, `.claude/settings.json`, `README.md`, `.github/dependabot.yml` |
| `python-release.yml`, `release-please-config.json`, `CHANGELOG.md` | Releases from Conventional Commits |
| `python-wiki.yml`, `docs/wiki/`, `scripts/gen-wiki.py`, `scripts/check-wiki.py` | The wiki, checked and mirrored to the GitHub wiki; for a service, `docs/openapi.json` and its breaking-change gate (decision 0005) |
| `python-tag-check.yml`, `scripts/tag-check.py` | Weekly PRs for dependencies pinned to a GitHub tag, which Dependabot can't update (decision 0002) |
| `scripts/checks.d/20-python.sh` | Wiki standard, version and lock file, inside base's `ci` |
| `Dockerfile`, `contrib/systemd/` | With `container_image`; with `contrib: [systemd]` |
| `docs/design/`, `docs/ai/`, `CONTRIBUTING.md`, `SECURITY.md`, `TODO.md` | Design records, prompts, the usual files |

## Setup notes

- **Required check:** branch protection names `ci` (base-ci.yml), whatever the stack.
- **Release PRs and CI:** PRs opened with the default `GITHUB_TOKEN` don't trigger CI. The organisation's
  release GitHub App (`RELEASE_APP_CLIENT_ID` variable, `RELEASE_APP_PRIVATE_KEY` secret) fixes that.
- **The wiki:** the GitHub wiki exists once its first page is created in the web UI; `python-wiki.yml`
  publishes `docs/wiki/` there from then on. Until then its publish job skips with a notice.

## Where this came from

Built from [metalayerlab/project-template](https://github.com/metalayerlab/project-template) `v0.1.23`'s
`layers/python/` and its Python-gated core files, as a new repository with no history.
[`docs/decisions/0001`](docs/decisions/0001-python-overlay.md) rebuilds the records that still apply.
Migrating an existing project: [`docs/migrating/`](docs/migrating/).

## License

[Unlicense](LICENSE).
