# 0001: The python stack overlay

Status: Proposed
Date: 2026-11-02
Authors: Stephen Cox

## Context

project-template made a Python project with `language: python`, through `layers/python/` and the core files
gated on it. template-base's decision **0001** (from the idea note **🥞 Stacked Copier Templates**, in the
brain's `vault/ideas/`) splits that template into a base and one stack overlay per project; where the two
disagree, template-base's 0001 wins. This repository is the overlay for Python. It is new, built from
project-template `v0.1.23`'s files, with no history. The old records are not imported; this record rebuilds
what still applies, and the originals stay in project-template's `docs/design/`.

What base doesn't carry, and code projects need, moves here: `kind`, `has_cli`, `container_image`,
`puid_pgid`, `contrib`, release-please and `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `TODO.md`, the
wiki (`docs/wiki/`, its generator and checker), the Dockerfile, `contrib/systemd/`, design records
(`docs/design/`), `docs/ai/`, markdownlint, and the bug and feature issue forms. Base never learns about any
of them.

## Decision

### Questions and answers

- **A Python project is base + this overlay** (+ template-container for an image's workflows and the
  docker and k8s manifests). It writes `.copier-answers.stack-python.yml` and fails unless base is
  `v2.0.0` or later (`base_check`): v2.0.0 adds the PR-template and issue-config slots and the
  `base_answers` pattern.
- **Asks** `package_name`, `kind` (`service`, `cli`, `library`), `python_version`, `port`, `extra_ports`,
  `health_path`, `container_image`, `image_extras`, `contrib` (`docker`, `k8s`, `systemd`), `puid_pgid`,
  `timezone`, `integration_ci`, `integration_extras`: project-template's Python questions, unchanged, so
  an old answers file splits into the new ones without a rename. **`has_cli` stays derived**
  (`kind in [service, cli]`): a service's `serve` command lives in its CLI.
- **Reads** `project_name`, `description`, `github_owner`, `code_owners`, `license`,
  `copyright_holder` and `personal_data_guard` from base's answers, and never asks them.
- **`base_answers`:** base's answers are recorded as an answer of this overlay, `base_answers`
  (`ask: false`, never prompted; a validator rejects a copy that differs from base's file), exactly as
  template-base's 0001 ("Overlays keep a copy of base's answers") and its stub stack do. `copier update`
  replays each version in an empty directory without `.copier-answers.base.yml`; the recorded copy is what
  the replays read. The values above are derived from `base_answers`, never from `_external_data`. The
  check passes in a replay (no base file, a recorded copy) and checks the file in the real render, so this
  overlay's first release is replay-safe and no project needs a `copier recopy`.
- **`contrib` stays this stack's answer**, docker and k8s included, although template-container renders
  their manifests. This stack's wiki pages, `.standard.toml`, release-please's `extra-files` and the
  manifest check need it, and the stack is applied before the container overlay, so it can't read that
  overlay's answers. template-container reads `contrib` from here. `scripts/checks.d/20-python.sh` fails
  when `contrib` names docker or k8s and `.copier-answers.container.yml` is missing.

### Slots

- `.agents/stack.md`: what project-template's AGENTS.md said for Python. Design records in `docs/design/`
  and `TODO.md`'s "Decided against", Don't read, the commands, the repository map, the conventions, the
  code Nevers, the Definition of done's lint, type and test commands, and the docs map. Base's AGENTS.md
  and this file share base's 9,000-character budget, and the skeleton keeps within 75% of it (a test).
- `stack-ci.yml`: the jobs that need the project installed. The test matrix (lint, format, mypy, pytest
  with its 80% floor, the import and CLI smoke test, `gen-wiki.py --check`), the integration job with
  `integration_ci` (was 0017), Markdown lint, and the Dockerfile and contrib manifest check. It runs under
  base-ci's `ci`, the one required check.
- `.gitignore` (Python's entries plus base's), `.pre-commit-config.yaml` (ruff, mypy, gen-wiki,
  `scripts/checks.sh`, gitleaks, conventional commits), `.claude/settings.json` (base's permissions plus
  uv, ruff, mypy, pytest and the wiki scripts), `README.md` (template-owned, as before) and
  `.github/dependabot.yml` (uv, actions, and docker with an image), `.github/pull_request_template.md`
  (project-template's code checklist, with base's "Template problem found?" item) and
  `.github/ISSUE_TEMPLATE/config.yml` (the wiki's Documentation link and base's security-advisory link).

### Checks, release and the wiki

- **`scripts/checks.d/20-python.sh`:** the wiki standard (`check-wiki.py`, `--strict` on Release PRs), the
  PEP 440 version against `.release-please-manifest.json`, and `uv lock --check`. These are stdlib checks,
  so base-ci's `checks` job runs them without installing the project. The context budget left
  `check-wiki.py` and `.standard.toml` for base's contract check.
- **`scripts/check-markdown.sh`:** markdownlint through Docker, which used to be check-docs-secrets'
  `docs` mode. It runs in `stack-ci.yml` and, locally, next to the secret scan when Docker is available.
- **`python-release.yml`:** release-please, plus the job that refreshes `uv.lock` on the Release PR. It no
  longer calls the image build: template-container's `container-build.yml` follows it by its name,
  `Release`.
- **`python-wiki.yml`:** "docs updated with the code", the `no-docs-needed` label and the mirror to the
  GitHub wiki. These stay outside `ci`, because the check reruns when a label changes (like `pr-title.yml`).
- **Drop-ins:** `bootstrap.d/20-python.sh` (`uv lock` and gen-wiki after `copier copy`, run by this
  overlay's own `_tasks`, because base's ran before it existed) and `post-update.d/20-python-uv-lock.sh`
  (the same after `copier update`).
- **Owned by name:** `python-*` workflows and `NN-python*` drop-ins. Every template-owned script and
  workflow says `Template-owned: template-python` in its first 12 lines, where base's contract looks.

### From project-template's records

| Old record | Here |
|---|---|
| 0005 Extra ports | `extra_ports`, unchanged; template-container's manifests publish them |
| 0012 Image extras | `image_extras`, unchanged: the Dockerfile is this stack's |
| 0017 Integration job | `integration_ci`, `integration_extras`, a job in `stack-ci.yml` |
| 0020 Thin config on interpose | Proposed again here as [0003](0003-interpose-config.md) |

The layer's named values and fragments stay as include files in `includes/`. They aren't rendered, and
they keep the rendered files reviewable line by line against project-template's. A converter checked that
project-template v0.1.23 and the carved-out files render identically for every Python kind.

## Alternatives considered

- **Docker, release, the wiki and contrib duplicated in each code overlay**, or a separate overlay for each.
  *Rejected* for one feature overlay, template-container, holding the image's build and cleanup workflows
  and the docker and k8s manifests. The Dockerfile, release-please and the wiki differ by language and
  stay here (Stephen's decision, 2026-11-02).
- **`contrib` asked by template-container:** this stack's wiki and release config need it before that
  overlay exists. *Rejected.*
- **The release workflow calling the image build** (`uses:` on the container overlay's file): a stack would
  name a feature overlay's file, and actionlint fails when it's missing. *Rejected* for `workflow_run` on
  `Release`.
- **Lint, types and tests in `checks.d`:** they need the project installed and its system packages (sluice's
  FUSE headers), which base-ci's `checks` job doesn't have. *Rejected* for `stack-ci.yml`.
- **`has_cli` as a question:** service-without-CLI isn't a real combination. *Rejected.*

## Consequences

- A Python project migrates by replacing `.copier-answers.yml` with base's and this overlay's files (and
  the container overlay's, with an image), in one reviewed PR, after a 3-way merge of each template file
  (`docs/migrating/`). `ci.yml`, `release-please.yml`, `wiki.yml` and `docker-*.yml` are removed by hand:
  Copier never deletes files. Branch protection names `ci`.
- A file a code stack can't extend, because base owns it: CODEOWNERS, so its per-file lines for
  `check-wiki.py` and `.standard.toml` are gone (the `*` owner still covers them).
- `gen-wiki.py` reads `Setting.is_list` with `getattr`. A project's `config.py` is its own
  (`_skip_if_exists`), and one from before list settings (sluice's, v0.1.15) has no `is_list`.

## Open questions

- **0020, a thin `config.py` on interpose:** still proposed in project-template. Recommendation: decide it
  here as its own record, now that the config skeleton lives in this overlay.
