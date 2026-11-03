# 0005: Commit the OpenAPI schema and check it in CI

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Proposed
Date: 2026-11-03
Authors: Stephen Cox

## Context

[0004](0004-fastapi-only.md) makes the OpenAPI schema the contract between services, and says that a
skeleton addition more than one service needs is a template change with its own record. The only check on
that contract today is `gen-wiki.py --check`, which compares the wiki's endpoint table: method, path and
summary. A changed request or response model, a new required parameter or a changed status code passes CI
unseen (#31, from qbt-rules' port to FastAPI; ferryman needs the same).

## Decision

For `kind: service`:

- **The schema is committed** as `docs/openapi.json`: `create_app(...).openapi()`, the app the wiki's
  endpoint table already reads, as JSON with a two-space indent and a final newline. `info.version` is
  written as `"snapshot"`: the schema changes with the code, not with every Release PR's version bump, so
  release-please never makes it stale.
- **`scripts/gen-wiki.py` writes and checks it** with the wiki's generated sections. One command
  (`uv run scripts/gen-wiki.py`) regenerates both, so the places that already run it keep the snapshot
  current without new wiring: `scripts/bootstrap.d/20-python.sh` (after `copier copy`),
  `scripts/post-update.d/20-python-uv-lock.sh` (after `copier update`), the pre-commit hook (which now also
  watches `docs/openapi.json`), and stack-ci.yml's Test job (`--check`). A stale snapshot fails with the
  command to run.
- **A breaking-change gate.** stack-ci.yml gets an `api-breaking` job, on pull requests only: it compares
  the PR's `docs/openapi.json` with the base branch's using [oasdiff](https://github.com/oasdiff/oasdiff)
  `breaking --fail-on ERR`. A breaking change fails unless the PR declares it, with `!` in its Conventional
  Commit title (`feat!: ...`) or a `BREAKING CHANGE:` line in its body, which is what makes release-please
  bump the major version. oasdiff is a release binary pinned by version and checked against its SHA-256,
  as hadolint and kubeconform are; about a second to download. A base branch without a snapshot (the PR
  that adds it) passes.

## Alternatives considered

- **A sibling `scripts/gen-openapi.py`.** Clearer name, but a second command to remember and three more
  call sites (bootstrap, post-update, CI) for what is the same "generated from the code, checked in CI"
  job. Rejected for now; split it out if the script grows.
- **Keep the real `info.version` and let release-please rewrite it** (a `json` extra-file). Couples the
  snapshot to the release config, and a local checkout that hasn't re-synced reports the old version.
- **Compare the live schema in CI without committing it.** No diff for a reviewer to read, and nothing for
  oasdiff to compare against on the base branch.
- **The `oasdiff/oasdiff-action`.** A Docker action, pinned by SHA but heavier, and its output is the same.

## Consequences

- Every service gains a generated file. Existing services (mitm-proxy) get it from `scripts/post-update.sh`
  on their next template update: commit it.
- Any change that touches a route's models now shows up as a `docs/openapi.json` diff in review.
- A PR that breaks the contract and says so passes, with a warning annotation; one that doesn't say so
  fails. The gate trusts the declaration; it doesn't check the version bump itself.
- oasdiff's version is in `stack-ci.yml`, not a lock file: bump it with its checksum.
- Wiki: HTTP-API-Reference mentions the committed schema (new projects; the page is the project's).

## Open questions

- Should the gate also fail on oasdiff's `WARN` level? Recommendation: no, `ERR` only; warnings are
  often deliberate and would push most contract changes into `feat!`.
