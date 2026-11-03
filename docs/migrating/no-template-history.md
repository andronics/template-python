# Migrating a project with no template history

For a repository that was never made from a template (no `.copier-answers*.yml`), so there is no old
render to 3-way merge against. The prompts in this folder (`interpose.md`, `sluice.md`, `mitm-proxy.md`)
assume project-template history; this guide replaces their steps 1 and 2 with a 2-way merge, and lists the
traps the first such migration hit. Worked example: andronics/trackie#10 (Flask service with an image,
deployed from homelab-k8s, ported to FastAPI in the same PR).

One reviewed PR. Work in a clone under `~/.cache/` (scratch off tmpfs), never in the project's own
checkout.

## 1. Survey before touching anything

Write down, from the sources, not from an earlier survey:

- **The version:** `gh release list`, `git ls-remote --tags origin`, and the version in the files. They
  can disagree (trackie's survey said 0.2.0; it had no tags and `0.1.0` in its files).
- **Every deployment:** image name and how it's pinned (tag or digest), port, probes (TCP or a path),
  uid and `fsGroup`, volumes and where the state actually is, and every environment variable it sets. If
  you can read the live system, check what is on the volume (trackie's PVC had `state/` and no config
  file, which decided the config migration).
- **Every client:** the paths, methods and JSON fields it reads (for trackie, qbt-rules'
  `TORRENT_FIELDS`/`ACCOUNT_FIELDS`).
- **CI secrets and variables** the old workflows read (`gh secret list`, `gh variable list`), and the
  GitHub wiki (`<repo>.wiki`), which `python-wiki.yml` will overwrite.

## 2. Seed the version, then apply the templates in place

```sh
git switch -c feat/stacked-templates
printf '{".": "%s"}\n' "$CURRENT_VERSION" > .release-please-manifest.json   # before the copy: it's _skip_if_exists
S=$(mktemp -d "${XDG_CACHE_HOME:-$HOME/.cache}/migrate.XXXXXX")
# $S/base.yml, $S/python.yml, $S/container.yml: the answers, as in the other prompts
uvx copier copy --trust --defaults --skip-tasks --overwrite --vcs-ref <base tag>      --data-file "$S/base.yml"      gh:andronics/template-base .
uvx copier copy --trust --defaults --skip-tasks --overwrite --vcs-ref <python tag>    --data-file "$S/python.yml"    gh:andronics/template-python .
uvx copier copy --trust --defaults --skip-tasks --overwrite --vcs-ref <container tag> --data-file "$S/container.yml" gh:andronics/template-container .
```

Answers that keep a deployment working: `owner_is_org: false` for a personal account; `health_path` = the
path the project already serves; `contrib` only for manifests that live in this repository (not
`k8s` when a homelab repository holds them); `multi_arch` matching the platforms the old workflow built;
`personal_data_guard: true` if the project had its own guard. `python_version` is the **minimum**, not
the only version: it becomes `requires-python = ">=…"`, ruff's target and the image's base, and
`stack-ci.yml` tests it and every newer version the template supports (`3.13` tests 3.13 and 3.14). Choose
the oldest version the project must run on.

## 3. Merge file by file (2-way)

`git status` lists what Copier wrote. For each file:

| The file is | Take |
|---|---|
| Template-owned (not in any `_skip_if_exists`) | The template's version, then carry the project's real customisations into a slot or drop-in: `scripts/checks.d/NN-<project>.sh`, `contrib/system-packages.txt`, `.gitignore` additions with a comment, `.gitleaks.toml` allow-list entries |
| A slot the project had its own version of (`README.md`, `.gitignore`, `dependabot.yml`) | The template's structure, with the project's content merged in, and no `<!-- guidance -->` left |
| Project-owned (`src/**`, `tests/**`, `CHANGELOG.md`, wiki pages) | The project's. Copier skipped the existing ones, but read the template's new ones (`api.py`, `cli.py`, `tests/unit/test_*.py`, `config.py`'s shape) and merge them in |
| An old workflow or script the templates replace | `git rm` it: `ci.yml`, `docker-*.yml`, a tag-push `release.yml`, `bump-version.sh`, `__version__.py` |

Then:

- **Tests** go to `tests/unit/`. Shared fixtures can stay in `tests/fixtures/`; merge `tests/conftest.py`
  (the template's `clean_env` and `write_config` plus the project's fixtures).
- **`CHANGELOG.md`** is project-owned, so Copier kept the old one. If it has no release entries, take the
  template's: the old header names the old release workflow.
- **The personal-data guard:** base's `check-personal-data.py` checks public IPs and a denylist read
  from the `PERSONAL_DATA_DENYLIST` secret. A project check it doesn't cover (trackie's tracker user IDs)
  goes in a `scripts/checks.d/` drop-in. Drop-ins run in the `checks` job, which gets **no secrets**: a
  denylist secret under another name needs a small project-owned workflow that runs base's guard with
  `PERSONAL_DATA_DENYLIST: ${{ secrets.<OLD_NAME> }}` until the owner copies it over (you can't read a
  secret's value).
- **gitleaks scans the history.** A fake key in an old test fails `Secret scan`: allow-list the exact
  value in `.gitleaks.toml`, with a comment, never a path.
- **Strict mypy now covers `tests/` and `scripts/`, and ruff selects more rules** (`S`, `RUF`, `T20`,
  `SIM`). Fix them: a `Protocol` for a test fake instead of `type: ignore`, `# noqa: S311` with a reason
  for non-security `random`, raw strings in `match=`.

## 4. Config on interpose (`service` and `cli`)

interpose (decision [0003](../decisions/0003-interpose-config.md)) names each variable from its key:
`a.b` is `<PREFIX>A_B`. A deployment sets variables, so:

- **Choose keys that keep every variable's name** (trackie: `ipt.cookie` for `TRACKIE_IPT_COOKIE`,
  `timeout` for `TRACKIE_TIMEOUT`). The YAML layout changes instead; check whether any deployment has a
  config file before deciding that's acceptable. Pin the full `(key, env)` list and the deployment's
  variables in `test_config.py`.
- **Interpose silently ignores unknown keys and variables.** Refuse what you renamed: an old layout's
  top-level sections, an old default config path, a renamed variable. Each is a `ConfigError` saying what
  to change.
- **No float settings:** a `str` setting with a number `check=`, converted in `load_config`.
- **Secrets** are `secret=True` and `Secret` in `Config`; call `reveal()` only where the value goes into a
  request.
- **The template's paths** are `/etc/<project>/config.yaml` and `/var/lib/<project>`. If a deployment
  mounts an old volume elsewhere, keep the template default and add a rule in `load_config`: setting unset
  and the old directory present means use it, with that reason as its source (`trackie config` shows it).
- **template-container's smoke test starts the image with no configuration.** A service that refused to
  start without credentials must start and report the problem instead (trackie: `error_kind: config` in
  `/health`).

## 5. Porting a service to FastAPI: prove nothing changed

The steps are in [README.md](README.md), "Porting a service to FastAPI". What the first port needed to
show it changed nothing:

1. **Before changing code**, write a script that builds the app's state from fixtures (fixed clock, real
   parsers, a failing source, a non-ASCII name) and saves each JSON endpoint's status, content type and
   bytes. Run it against `main` in a worktree with the old dependencies.
2. **Port.** To keep a client byte-compatible, send the documents with a `JSONResponse` subclass that
   writes what the old framework wrote. Flask's `jsonify` is
   `json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"`. Declare the
   Pydantic models as `response_model` (for the OpenAPI schema and the wiki table) and return the response
   object, which FastAPI passes through without re-serialising. Then validate the real documents against
   the models in a test with `strict=True` and `extra="forbid"`.
3. **Run the same script against the new app** and `cmp` the bytes. Commit a small golden test of the
   serialiser, and a contract test of the fields and JSON types each client reads.
4. **Background threads** start in the lifespan: register them with `threads.add(...)` in `create_app`
   (decision [0006](../decisions/0006-lifespan-threads.md)). An app built with an injected object (tests)
   never starts them; `/readyz` answers 503 naming a thread that isn't alive.
5. **Run the deployed image (its pinned digest) and the new one side by side**, as the deployment does:
   same uid, same volume layout and variables, with the upstream URLs pointing at a closed local port so
   nothing real is contacted. Compare the endpoints, ignoring that run's timestamps.

## 6. Wiki

Import every page of `<repo>.wiki` into `docs/wiki/` **before the first merge**, keeping page names:
`python-wiki.yml` replaces the GitHub wiki with that folder on every push to `main`. Merge the content into
the template's required headings (`docs/wiki/.standard.toml`), keep extra pages linked from `_Sidebar.md`,
take the template's `Release-Process.md`, and fill the generated blocks with `uv run scripts/gen-wiki.py`.
No `<!-- guidance -->` may remain: Release PRs run `check-wiki.py --strict`.

**Page names.** GitHub's web editor saves a hyphen typed in a page title as U+2010 (`‐`), so an imported
page can be `In‐Depth-Configuration.md` where the standard requires `In-Depth-Configuration.md`: two pages
with the same displayed title. The standard has no alias or redirect. `check-wiki.py` finds a required page
by its exact name, and a GitHub wiki can't redirect. So:

1. `git mv` the page to the standard's ASCII name and fix the links in `docs/wiki/` (the checker reports
   each link to a missing page).
2. Look for outside links to the old name: the README, docs, issues, other repositories
   (`gh search code '<old name>'`). `python-wiki.yml` deletes every page that isn't in `docs/wiki/`, so
   after the first merge the old URL is a "create this page" prompt.
3. If any exist, keep the old name as a one-line stub, `Moved to [In-Depth Configuration](In-Depth-Configuration).`
   The checker allows extra pages but wants every page linked from `_Sidebar.md`, so link the stub from
   the sidebar too, at the end (`Moved: [In‐Depth-Configuration](In‐Depth-Configuration)`). Remove both
   once nothing links to it.

## 7. A staged migration: the old code keeps running

A large port can land in several PRs: the templates first, with the old server and CLI still running, then
config, the API and the CLI one at a time (andronics/qbt-rules#36 kept Flask serving). Until each step lands,
some template files describe code that isn't running yet:

- **Generated wiki sections.** `gen-wiki.py` fills the `settings`, `cli` and `http-api` blocks from the
  skeleton's `config.py`, `cli.py` and `api.py`, which aren't what runs. Delete a block's
  `<!-- generated:start/end -->` markers (keep the old hand-written table) until the step that ports that
  code, and put them back in that step's PR. `gen-wiki.py` only touches text between markers, and
  `check-wiki.py` doesn't require them. Write the plan in `TODO.md`.
- **`docs/openapi.json`** is always written from the skeleton's `create_app` and can't be switched off. Say
  in the PR and `TODO.md` that it describes the skeleton until the API port, whose PR will change it (the
  `api-breaking` job then compares against the skeleton's schema; declare a breaking change with `feat!:`).
- **The working directory.** The image's runtime stage sets no `WORKDIR` up to template-python v2.4.0, so
  the process runs in `/`: legacy code that resolves `./config` silently reads an old `/config` mount if
  one is still attached. Make legacy paths absolute (or derive them from `state_dir`), and remove the old
  volume from the deployment rather than relying on it being absent. (andronics/template-python#40 sets
  `WORKDIR /var/lib/<project>`, decision 0009.)
- **`contrib/docker/compose.yml`** (template-container's) pins `image: <image>:0.0.0`. The
  `# x-release-please-version` comment makes the first release PR write the real version, so leave the line
  alone. Until then, build the tag locally (`docker build -t <image>:0.0.0 .`) or override `image:` in an
  untracked `compose.override.yml`.
- **Its comment suggests `docker exec <project> <project> config`.** The `config` command arrives with the
  Typer CLI. Leave the comment, which is template-owned and right once the CLI port lands.
- **`CMD ["serve"]`** (and the k8s `args: ["serve"]`): the legacy entry point must accept `serve` from the
  first PR. qbt-rules added it as a synonym of `--serve`.
- **The HEALTHCHECK** polls `http://127.0.0.1:${<PREFIX>LISTEN_PORT:-<port>}<health_path>`, and the image
  sets `<PREFIX>LISTEN_HOST=0.0.0.0`. Legacy code reads neither: answer `port` with the port the old server
  listens on by default and `health_path` with a path it serves, make it bind every interface itself, and
  have a deployment that changes the port set `<PREFIX>LISTEN_PORT` to the same value as the legacy
  variable. Each mismatch disappears when config moves onto interpose.
- **`health_path` in the API-port step.** Once FastAPI serves the API, answer `health_path: /healthz` again
  (the skeleton's liveness route; keep the old path as an extra route until its callers move). Update
  template-python at its pinned version with the new answer, then run `copier update` of template-container
  at *its* pinned version too: template-container keeps its own copy of the stack's answers
  (`stack_answers` in `.copier-answers.container.yml`) and renders `health_path` from that copy into
  `container-build.yml`'s smoke test, the compose file and the k8s probes. The update rereads the stack's
  answers file because the stale copy fails its validator. Both commands, with the `_commit` each answers
  file records:

  ```sh
  uvx copier update --trust --defaults --skip-tasks --vcs-ref <python _commit> -a .copier-answers.stack-python.yml -d health_path=/healthz
  uvx copier update --trust --defaults --skip-tasks --vcs-ref <container _commit> -a .copier-answers.container.yml
  ```

  Check `git diff` shows `/healthz` in the Dockerfile's HEALTHCHECK and in the container files.
  (andronics/qbt-rules' step 4c: one commit for each update.)
- **The legacy app beside FastAPI.** When FastAPI serves part of the API and the old WSGI app (Flask) the
  rest, mount the old one through `a2wsgi.WSGIMiddleware` on each path it still serves, never at `/`. Starlette
  prefers a route whose path matches over one whose path and method match only partly, so with a mount at
  `/` a request to a FastAPI route with the wrong method goes to the legacy app: every 405 silently becomes
  its 404. One route per legacy path keeps the 405s, and keeps unknown paths on FastAPI's 404:

  ```python
  legacy = WSGIMiddleware(flask_app)
  for path in ("/", "/login", "/jobs/{job_id}", "/static/{path:path}"):
      app.router.routes.append(Route(path, legacy, include_in_schema=False))
  ```

## 8. Check, open the PR, merge

Everything in `.agents/stack.md`'s Definition of done, plus `check-wiki.py --strict`, the image build, and
a container run that answers the health path and each client's endpoint. Title: `feat!:` if a config
file, a variable or a minimum Python version changed, with a `BREAKING CHANGE:` footer in the squash body.

## 9. After the merge

- `Release` runs release-please from the seeded version over the whole history (with no tags, every
  earlier commit lands in the first changelog; that's right, since none was released). It needs the
  release App (`RELEASE_APP_CLIENT_ID` variable, `RELEASE_APP_PRIVATE_KEY` secret, Tagwarden installed on
  the repository) or "Allow GitHub Actions to create and approve pull requests". With neither, it pushes
  its branch and fails at "not permitted to create or approve pull requests"; re-run it once one is set.
  template-update.yml wants Courier (`PIN_BUMP_APP_*`). Installing Apps is the owner's step.
- `python3 scripts/repo-metadata.py` sets the About box from `.github/repository.toml`.
- Deployments pinned by digest change nothing until the digest is bumped: bump it after the release image
  is built, and keep the previous digest as the rollback.
