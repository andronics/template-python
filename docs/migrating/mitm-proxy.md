# Migrating mitm-proxy to template-base + template-python + template-container

Paste everything below the line into a Claude Code session opened in `metalayerlab/mitm-proxy`.

---

Migrate this repository from `metalayerlab/project-template` (v0.1.17) to the stacked templates:
template-base v2.0.2, then template-python v2.0.0, then template-container v2.0.0. It's a service with an image and docker, k8s and systemd manifests (template-container too).
Why: template-base's `docs/decisions/0001-stacked-templates.md`, template-python's
`docs/decisions/0001-python-overlay.md` and template-container's `docs/decisions/0001-container-overlay.md`.

This is one reviewed PR that replaces `.copier-answers.yml` with `.copier-answers.base.yml`, `.copier-answers.stack-python.yml` and `.copier-answers.container.yml`. Don't push to `main`. Open
the PR from a branch and stop there for review. Copier writes the new `.copier-answers.*.yml` files itself; never edit them by hand.

## 1. Render what the old template made, in a scratch directory

```sh
git switch -c chore/stacked-templates
mkdir -p "${XDG_CACHE_HOME:-$HOME/.cache}"   # scratch goes here, not in /tmp (a small tmpfs)
S=$(mktemp -d "${XDG_CACHE_HOME:-$HOME/.cache}/migrate.XXXXXX")
cat > "$S/old.yml" <<'EOF'
code_owners: '@metalayerlab/maintainers'
container_image: true
contrib:
- docker
- k8s
- systemd
dependabot_automerge: 'off'
description: Async Python MITM proxy with a self-signed CA — HTTP/1.1 & HTTP/2, pluggable middleware for inspecting and rewriting traffic in flight.
extra_ports:
- 3128
github_owner: metalayerlab
health_path: /healthz
image_extras: []
kind: service
language: python
license: Unlicense
multi_arch: true
package_name: mitm_proxy
personal_data_guard: true
port: 8080
project_name: mitm-proxy
puid_pgid: false
python_version: '3.13'
timezone: Europe/London
EOF
cat > "$S/base.yml" <<'EOF'
project_name: mitm-proxy
description: Async Python MITM proxy with a self-signed CA — HTTP/1.1 & HTTP/2, pluggable middleware for inspecting and rewriting traffic in flight.
github_owner: metalayerlab
code_owners: '@metalayerlab/maintainers'
license: Unlicense
dependabot_automerge: 'off'
personal_data_guard: true
EOF
cat > "$S/python.yml" <<'EOF'
package_name: mitm_proxy
kind: service
python_version: '3.13'
port: 8080
extra_ports:
- 3128
health_path: /healthz
container_image: true
image_extras: []
contrib:
- docker
- k8s
- systemd
puid_pgid: false
timezone: Europe/London
EOF
cat > "$S/container.yml" <<'EOF'
multi_arch: true
EOF
# A: what the old template made, for the 3-way merge in step 2.
uvx copier copy --trust --defaults --skip-tasks --vcs-ref v0.1.17 --data-file "$S/old.yml" gh:metalayerlab/project-template "$S/A"
```

The answers above are this repository's current ones, split by owner (base's identity; python's stack;
`multi_arch` for the container overlay). Nothing is renamed and nothing is new.

## 2. Apply the new templates in place, then 3-way merge what this repository had changed

```sh
uvx copier copy --trust --defaults --skip-tasks --overwrite --vcs-ref v2.0.2 --data-file "$S/base.yml" gh:andronics/template-base .
uvx copier copy --trust --defaults --skip-tasks --overwrite --vcs-ref v2.0.0 --data-file "$S/python.yml" gh:andronics/template-python .
uvx copier copy --trust --defaults --skip-tasks --overwrite --vcs-ref v2.0.0 --data-file "$S/container.yml" gh:andronics/template-container .
```

Copier writes each template file over the project's, and leaves the `_skip_if_exists` ones alone (`src/`,
`tests/`, most wiki pages). Where this repository had changed the old template's version of a file, that
overwrite dropped its edits. So, for each file Copier changed whose committed version differs from what the
old template made (`$S/A`), redo it as a 3-way merge, A → the new version, onto ours (what `copier update`
does):

```sh
python3 - "$S" <<'PY'
import subprocess, sys
from pathlib import Path
A = Path(sys.argv[1]) / "A"
changed = [l[3:] for l in subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True,
                                         check=True).stdout.splitlines() if l[:2].strip() == "M"]
conflicts = []
for rel in changed:
    ours = subprocess.run(["git", "show", f"HEAD:{rel}"], capture_output=True, check=True).stdout
    old = A / rel
    if not old.is_file() or old.read_bytes() == ours:
        continue  # the project never changed this file: the new version stands
    new = Path(rel).read_bytes()
    theirs = Path(sys.argv[1]) / "new" / rel  # the new version, kept for a conflict
    theirs.parent.mkdir(parents=True, exist_ok=True); theirs.write_bytes(new)
    Path(rel).write_bytes(ours)
    if subprocess.run(["git", "merge-file", "-L", "ours", "-L", "old template", "-L", "new templates",
                       rel, str(old), str(theirs)]).returncode:
        conflicts.append(rel)
    print("merged" if rel not in conflicts else "CONFLICT", rel)
print("conflicts:", conflicts or "none")
PY
git rm -q .copier-answers.yml .github/workflows/ci.yml .github/workflows/docker-build.yml .github/workflows/docker-cleanup.yml .github/workflows/release-please.yml .github/workflows/wiki.yml
```

The last line removes the files the old template made and no new template makes. Copier never deletes
files: `ci.yml` became base-ci.yml + stack-ci.yml, `release-please.yml` became python-release.yml,
`wiki.yml` became python-wiki.yml, `docker-*.yml` became container-*.yml.

**Expected:** `.gitleaks.toml`, `Dockerfile`, `contrib/docker/compose.yml`, `contrib/k8s/{config,deployment,kustomization,networkpolicy,service}.yaml` and `pyproject.toml`. All of them merge cleanly, and mitm-proxy's edits are kept.
Then check `git status`: nothing under `src/`, `tests/`, `docs/design/` or this repository's own files
may change. If anything does, restore it with `git checkout -- <path>` and say so in the PR.

## 3. Carry over what the templates can't

- Nothing to carry over by hand: the 3-way merge keeps every edit.

## 4. Refresh, check, open the PR

```sh
sh scripts/post-update.sh          # uv lock and the generated wiki sections
sh scripts/checks.sh               # base's contract, the wiki standard, version and lock
uv sync --locked && uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
uv run scripts/gen-wiki.py --check
scripts/check-manifests.sh         # if present
scripts/check-docs-secrets.sh && scripts/check-markdown.sh   # with Docker
```

- `scripts/post-update.sh` changes `docs/wiki/In-Depth-Configuration.md` (see above), and nothing else.
- mitm-proxy was made from v0.1.17. `gen-wiki.py` now marks list settings `*(empty list)*` and adds "A list: YAML, or comma-separated.", so `scripts/post-update.sh` regenerates the settings table in `docs/wiki/In-Depth-Configuration.md`. That's intended: commit it.

Commit as `chore: move to template-base, template-python and template-container` and open the PR. In the
PR body, list the conflicts you resolved and anything from step 3.
Then remove the scratch directory, which nothing cleans up for you: `rm -rf "$S"`.

## 5. Branch protection (Stephen's step, not the agent's)

The required check is now the single `ci` job (base-ci.yml), whatever the stack. The old job names
(`Test (Python 3.13)`, `Version and lock file`, ...) no longer exist. mitm-proxy has **no branch protection or
ruleset today** (checked 2026-11-02), so this is a new rule, not a change. Once this PR's first `ci` run has
reported, add a `main` ruleset that requires `ci` in the repository settings (Rules → Rulesets). Do it in
the same step as the merge, so no PR waits on a check that never runs.

## 6. After the merge

- The first `ci` run on `main` is green: `gh run list --workflow base-ci.yml --branch main --limit 1`.
- `copier update` is a no-op for each template: for each of `.copier-answers.base.yml`, `.copier-answers.stack-python.yml` and `.copier-answers.container.yml`, run
  `uvx copier update -a <file> --trust --skip-tasks --defaults` and confirm `git status` is clean.
- `Template update` (template-update.yml) runs: `gh workflow run template-update.yml`. It opens no PR while
  every template is current.
- The release path still works: the next Release PR's `ci` is green, and after its release `container-build.yml` runs from `Release` and pushes the `:X.Y.Z` and `:latest` tags.
