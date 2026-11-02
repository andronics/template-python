# 0002: A tag-check workflow for git-tag-pinned dependencies

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Accepted (2026-11-02)
Date: 2026-11-02
Authors: Stephen Cox

## Context

[metalayerlab/interpose](https://github.com/metalayerlab/interpose) v0.1.0 is tagged, and it is
distributed by git tag only, never PyPI. A consumer depends on it as
`"interpose @ git+https://github.com/metalayerlab/interpose@v0.1.0"`. [0003](0003-interpose-config.md)
makes every generated CLI and service such a consumer, so every one of them needs a way to hear about
`v0.1.1`.

Dependabot's `uv` ecosystem, already in every Python project, can't do it (interpose's design 0001, open
question 4, checked 2026-11-02 against dependabot-core `85379652`):

- Its parser keeps a PEP 508 requirement's name and specifier and drops the URL
  ([`uv/helpers/lib/parser.py`](https://github.com/dependabot/dependabot-core/blob/85379652/uv/helpers/lib/parser.py#L35-L51)),
  so it looks `interpose` up on PyPI, finds nothing and opens no PR. Git-sourced `uv.lock` entries are
  skipped. [#16129](https://github.com/dependabot/dependabot-core/issues/16129) is open;
  [#16132](https://github.com/dependabot/dependabot-core/pull/16132) (merged) lists the case as not covered.
- [#16151](https://github.com/dependabot/dependabot-core/pull/16151) (open, in review) would bump
  `tag = "..."` in `[tool.uv.sources]` only, not the PEP 508 form 0003 uses.

**Name squatting.** Because Dependabot asks PyPI for the bare name, anyone who registers `interpose` there
(it's free today: `pypi.org/pypi/interpose/json` is a 404) would be proposed as an "update". uv itself is
safe: a requirement with a direct URL is resolved from that URL and never from an index, and the URL is in
the built wheel's own metadata (`Requires-Dist: interpose @ git+https://...`), so pip installing the
project's wheel takes it from GitHub too. The exposure is a reviewer merging a Dependabot PR. A
`[tool.uv.sources]` pin would be worse: the metadata would say the bare `interpose`, and any non-uv
installer would take PyPI's.

## Decision

### What ships

A template-owned workflow, `.github/workflows/python-tag-check.yml`, and its script,
`scripts/tag-check.py` (stdlib only: `tomllib`, `urllib`, `re`, `subprocess`), both marked
`Template-owned: template-python`, in **every** Python project, whatever its `kind`. No Copier question:
with no tag-pinned git dependency it finds nothing, writes "no tag-pinned git dependencies" to the job
summary and exits 0, in a few seconds a week. A project that adds its own git dependency later is covered
without a `copier update -d`.

### What it finds

`scripts/tag-check.py` reads `pyproject.toml` and collects, from `[project].dependencies`,
`[project.optional-dependencies]` and `[dependency-groups]`:

- a PEP 508 direct reference to GitHub pinned to a tag:
  `NAME[extras] @ git+https://github.com/OWNER/REPO[.git]@TAG[; markers]`
- and, for #16151's form, a `[tool.uv.sources]` entry `NAME = { git = "https://github.com/OWNER/REPO", tag = "TAG" }`.

`TAG` must be `vMAJOR.MINOR.PATCH` (the `v` optional). A branch, a commit or a pre-release pin is listed in
the summary as skipped, never bumped. A PEP 508 `@REF` doesn't say whether it is a branch or a tag: a hex
`REF` of 7 to 40 characters is taken as a commit, and any other non-`vX.Y.Z` one is reported as a branch.

### How it checks

For each dependency, `GET /repos/OWNER/REPO/tags` (paginated) and pick the highest tag that is strict
semver with no pre-release and is greater than the pin. The tag's own name is written, since that is
what exists; the pin's `v` style only decides between two tags for the same version (`v1.2.0` and `1.2.0`). Major bumps (and
`0.x` minor bumps, breaking below 1.0) are proposed like any other; the PR title says so.

### How it bumps: one PR per dependency

On branch `tag-check/NAME`, from `main`:

1. Replace the pinned tag in `pyproject.toml` as text, only in the line that matched (no TOML rewrite, so
   formatting and comments stay).
2. `uv lock --upgrade-package NAME`. Nothing else moves in `uv.lock`.
3. Commit both as `chore(deps): bump NAME from vOLD to vNEW` (Dependabot's `chore(deps)` prefix, as this
   overlay's `dependabot.yml` sets it), force-push the branch, and open the PR or edit the open one's title
   and body. A newer tag rewrites the same branch, so there is never more than one PR per dependency.
   When the pin is already current, an open PR for it is closed with a comment.
4. The body links `https://github.com/OWNER/REPO/compare/vOLD...vNEW` and the release, and says whether CI
   ran (below).

Weekly, Monday 05:00 UTC (an hour before base's `template-update.yml`), and `workflow_dispatch`.
`concurrency: tag-check`, `permissions: contents: write, pull-requests: write`.

### How it authenticates

As `python-release.yml` and base's `template-update.yml` do: when `vars.RELEASE_APP_CLIENT_ID` is set,
`actions/create-github-app-token` (with `RELEASE_APP_PRIVATE_KEY`, `owner: ${{ github.repository_owner }}`);
otherwise `github.token`.

- **With `GITHUB_TOKEN`, the PR's CI doesn't run** (events it causes start no workflows), so `ci` never
  reports and the PR can't merge. The PR body says so, and that closing and reopening it runs CI.
- **`GITHUB_TOKEN` can open the PR only if** the repository allows it (*Settings → Actions → Allow GitHub
  Actions to create and approve pull requests*), as for `template-update.yml`; otherwise the PR request
  fails and the job fails with it.
- **A private dependency** needs the App, installed on that repository: `GITHUB_TOKEN` can read only the
  current one. Without access, the tags request fails, and the job fails naming the dependency, so the
  scheduled run's failure is seen rather than skipped quietly. `uv lock` uses the same token
  (`git config url.https://x-access-token:TOKEN@github.com/.insteadOf`).

### Squatting, closed for interpose

When 0003 adds interpose, `dependabot.yml`'s `uv` entry gets `ignore: [{dependency-name: interpose}]`, so
Dependabot never proposes PyPI's `interpose`. A project's own git dependencies aren't known to the template;
the job summary lists each one with "Dependabot looks this name up on PyPI: treat a Dependabot PR for it as
suspect", and the wiki's Release-Process page (template-owned) says the same.

### Lifetime

Until Dependabot updates the PEP 508 form. If #16151 lands it covers only `[tool.uv.sources]`, which 0003
doesn't use (Context), so this workflow stays.

## Alternatives considered

- **In template-base, as a generic workflow.** It has to parse `pyproject.toml` and run `uv lock`, and base
  never names a stack. A base workflow with a `tag-check.d/` drop-in for each stack's bump would be a new
  base contract and minor release for one consumer; template-typescript's npm git dependencies are
  Dependabot's npm ecosystem's job. *Rejected* for this overlay; lift it if a second stack needs it.
- **A Copier question (`tag_check: bool`).** It adds a render variant to guard a job that costs nothing when
  idle, and a project that adds a git dependency later would need `copier update -d` to get it.
  *Rejected* for a no-op run.
- **Wait for Dependabot** (#16129, #16151). No date, and #16151 doesn't cover the form 0003 uses.
  *Rejected.*
- **Renovate**, which updates git tags. A second dependency bot beside Dependabot, with its own config and
  App, for one dependency. *Rejected.*
- **Switch to `[tool.uv.sources]` so #16151 would cover it.** The built metadata then names a bare
  `interpose`, which a non-uv installer takes from PyPI: it trades a bot gap for a squatting hole.
  *Rejected.*
- **Register a placeholder `interpose` on PyPI.** Closes the Dependabot path for everyone, but interpose's
  0001 rejected owning a PyPI name, and the `dependabot.yml` ignore already closes it. *Rejected*
  (resolved question 4).
- **Dispatch `ci` on the branch when the token is `GITHUB_TOKEN`** (`gh workflow run base-ci.yml --ref`,
  which `GITHUB_TOKEN` may do). It works, but this overlay would name base's workflow file and depend on
  its `workflow_dispatch` trigger. *Rejected* for the close-and-reopen note (resolved question 2).
- **One PR for all tag-pinned dependencies.** One bad bump blocks the rest; Dependabot's one PR per
  dependency is what reviewers already expect. *Rejected.*
- **Inline Python in the workflow** (as `template-update.yml`'s `plan`). The parser and the semver choice
  want unit tests, and a script can be run locally (`--dry-run`). *Rejected.*

## Consequences

- **Copier questions:** none.
- **What projects get**, existing ones through their next template update (both files are template-owned,
  so `copier update` reaches them): the workflow, the script, the Release-Process paragraph. With 0003, the
  `dependabot.yml` ignore. Nothing changes for a project without tag-pinned git dependencies but one weekly
  no-op run.
- **Tests here** (`tests/test_tag_check.py`): the template's `scripts/tag-check.py` (copied verbatim, so
  it is tested as it is, without a render) parses a fixture `pyproject.toml` (each form, extras and markers,
  a branch, commit and pre-release pin, none at all), picks tags and rewrites lines, and runs `--dry-run
  --tags-from`. A full run goes against a fake GitHub API (a local HTTP server, paginated tags), a local
  bare `origin` and a stub `uv`, and asserts the pushed branch, its commit and diff, and the PR requests
  (open, edit, close, a 404). Each render runs the script as a no-op; actionlint covers the workflow.
- **Release:** `feat:` in template-python, a minor release.
- **`.agents/stack.md`:** unchanged. The workflow is a CI concern; the wiki's Release-Process page
  documents it.
- **Scheduled workflows stop** after 60 days without activity in a public repository, as
  `template-update.yml` does; nothing new.
- **Rollback:** delete the workflow in a template release; open PRs are closed by hand.

## Resolved questions

Stephen accepted every recommended answer on 2026-11-02.

1. **Ship it before 0003 is approved?** Yes: sluice and mitm-proxy depend on interpose as soon as their
   switches merge, before any template change, so they need it first.
2. **With `GITHUB_TOKEN`, is "close and reopen" in the PR body enough?** Yes, without dispatching CI or
   requiring the App: every metalayerlab and andronics repository that matters has the release App, and
   the alternative couples this overlay to base's `base-ci.yml`.
3. **Pick the highest tag, or the highest in the same major?** The highest, with "breaking" in the title
   for a major (or `0.x` minor) bump: interpose is below 1.0, where every minor can break, and holding back
   would hide the release that matters.
4. **Register a placeholder `interpose` on PyPI?** No: the `dependabot.yml` ignore closes the only path
   that would install PyPI's package, at no cost. Revisit if interpose gains consumers outside these
   templates.
