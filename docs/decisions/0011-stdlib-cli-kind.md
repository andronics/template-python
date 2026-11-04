# 0011: A standard-library-only kind, `stdlib-cli`

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Approved (2026-11-04)
Date: 2026-11-04
Authors: Stephen Cox
Partly superseded by: [0012](0012-stdlib-seeded-test.md): the seeded test's usage-error code and how it runs the program

## Context

Every `kind` with a command today is built on third-party code: `cli` and `service` get a Typer CLI
(`cli.py`), a settings engine on interpose ([0003](0003-interpose-config.md)) and PyYAML, and `service` adds
FastAPI and uvicorn ([0004](0004-fastapi-only.md)). Some programs must not import anything from PyPI: a tool
that runs as root, one that runs before any virtualenv exists, or one copied onto a host as a single file.
They run with the system interpreter as `python3 -IS`: `-I` ignores every `PYTHON*` variable, the user's
site folder and the script's own folder; `-S` skips `site`, so no site-packages folder or `.pth` file is
read. Only the standard library can be imported.

The first such project is andronics/rootctl, an allowlisted root wrapper (its design record 0001, §2). It
was rendered as `kind: cli` (template-python v2.4.4) and then took the CLI apart: `dependencies = []`, no
`cli.py`, `config.py` or `contrib/rootctl.example.yaml`, one stdlib-only program module
`src/rootctl/rootctl.py` whose first line is `#!/usr/bin/python3 -IS`, and a release asset that is that
file byte for byte. A second project, andronics/passfill, follows the same `-IS` rules. After that,
these template-owned files are wrong for it:

| File | What it says that isn't true there |
|---|---|
| `.agents/stack.md` | `src/<pkg>/` holds `config.py` and `cli.py` (Typer); every setting goes through `config.SETTINGS`; the CLI writes with `typer.echo` |
| `docs/wiki/Release-Process.md` | `__version__` reads the installed package metadata; interpose bumps come from the tag check |
| `.github/dependabot.yml` | the `uv` entry ignores `interpose`, which it doesn't depend on |
| `docs/wiki/.standard.toml` | `docs_touched` watches `src/*/config.py` and `src/*/cli.py`, which don't exist, so a change to the program needs no docs |
| `scripts/gen-wiki.py` | imports `typer` and `<pkg>.cli` for the `cli` and `settings` blocks |
| `pyproject.toml` (merged) | interpose, PyYAML and Typer in `dependencies`; `allow-direct-references`; `types-pyyaml` |

rootctl works around each: its own record wins over `stack.md` where they differ; a mypy override
(`ignore_missing_imports` for `typer`, `rootctl.config`, `rootctl.cli`) and a ruff `known-first-party` keep
`gen-wiki.py` type-checking and sorted; its version is a literal
(`__version__ = "x.y.z"  # x-release-please-version`) listed in `release-please-config.json`'s
`extra-files`, because an installed single file has no package metadata. Every template update merges
against those workarounds, and the next stdlib-only project would repeat them.

Two facts about `-IS` shape the decision (checked with Python 3.14.7):

- **A file run by path cannot import its sibling modules.** `-I` implies `-P`, so the script's folder is not
  on `sys.path`: `python3 -IS app/main.py` fails `import sib` with `app/sib.py` beside it. So a program that
  must run as `python3 -IS <file>` is one module, or a zipapp (`python3 -IS app.pyz` does import its
  members).
- **Package metadata is not there.** The program isn't installed as a distribution, so
  `importlib.metadata.version()` raises `PackageNotFoundError`, and today's skeleton prints `0+unknown`.

## Decision

### The shape: a fourth `kind`, `stdlib-cli`

`kind` gains a choice, `"stdlib-cli: command-line tool, standard library only (argparse), runs as python3
-IS": stdlib-cli`. Derived, never asked:

- `has_cli` becomes `kind in ['service', 'cli', 'stdlib-cli']`: there is a command, a CLI-Reference page,
  an In-Depth-Configuration page and a `[project.scripts]` entry.
- `stdlib_only` (new) is `kind == 'stdlib-cli'`. Every file that is Typer- or interpose-specific today and
  gated on `has_cli` is gated on `has_cli and not stdlib_only` instead.

Not asked for `stdlib-cli`: `container_image` (its `when` becomes `kind in ['service', 'cli']`), so neither
`image_extras` nor `puid_pgid`; `port`, `extra_ports`, `health_path`, `contrib` and `timezone` are already
service-only; `integration_extras` (a stdlib-only project has no optional dependencies to install).
`integration_ci` is still asked.

### The program: one stdlib-only module named after the package

- **`src/<pkg>/<pkg>.py`** (seeded once, `src/**`) is the whole program: argument parsing, `main()` and
  everything it calls. Its first line is `#!/usr/bin/python3 -IS` (one word for the flags: Linux passes a
  shebang's arguments as one string). It imports only the standard library and nothing from `<pkg>`, so
  `python3 -IS src/<pkg>/<pkg>.py` runs it and a release can ship it as one file.
- **`__init__.py`** re-exports `__version__` from it; **`__main__.py`** calls its `main()`; both exist for
  `uv run`, tests and `python -m <pkg>`, and are never needed by the installed file.
- **`[project.scripts]`** `<project> = "<pkg>.<pkg>:main"`, so `uv run <project>` works in development.
- A project may split the program later (into a zipapp built at release, for instance); that is its own
  design record. The template ships the one-file shape because it is what `-IS` runs without a build step.

### The CLI: argparse

- The skeleton's parser is `argparse.ArgumentParser(prog="<project>", allow_abbrev=False)` with `--version`
  (prints `<project> X.Y.Z`) and one example subcommand. `allow_abbrev=False` because an abbreviation
  accepted silently (`--ver` for `--version`) is the surprise a strict tool avoids; argparse already exits
  2 on a usage error, matching the template's "one line, exit 2" rule.
- Output goes through `sys.stdout.write` and `sys.stderr.write` (ruff's `T20` forbids `print` in `src/`).
- The parser is project-owned code: a project may replace it, as rootctl does with a hand parser for a
  fixed grammar. Nothing template-owned imports it.

### Configuration: none in the skeleton

No `config.py`, no settings engine, no example config file. The skeleton takes its input from arguments.
`stack.md` states the rule for a project that needs more: environment variables named
`<PREFIX><KEY>`, read in one place; a file, if any, is TOML read with `tomllib`; precedence documented on
In-Depth-Configuration. The page stays in the wiki standard with its headings (a tool's input is still
configuration: rootctl documents its allowlist there), with no generated `settings` block.

### The version: a literal, bumped by release-please

- The program file holds `__version__ = "0.0.0"  # x-release-please-version`.
- `release-please-config.json` lists it in `extra-files` as `{"type": "generic", "path":
  "src/<pkg>/<pkg>.py"}`, so the Release PR rewrites it with `pyproject.toml` and the manifest.
- `scripts/checks.d/20-python.sh` adds one check for `stdlib-cli`: the literal equals `pyproject.toml`'s
  version (as it already checks the manifest).
- `test_version.py` (seeded) drops the `0+unknown` alternative: the literal is always a real version.

### What CI enforces

- **`scripts/check-stdlib.py`** (new, template-owned, stdlib only, rendered for `stdlib-cli`), run in
  `stack-ci.yml`'s test matrix (so each supported Python checks against its own `sys.stdlib_module_names`)
  and listed in the Definition of done. It fails if:
  1. `pyproject.toml`'s `[project] dependencies` is not empty, or it has
     `[project.optional-dependencies]`;
  2. any module in `src/<pkg>/` imports (anywhere in the file, including inside a function) a top-level
     module outside `sys.stdlib_module_names`, or calls `importlib.import_module`
     or `__import__` with anything but a string literal naming a standard-library module;
  3. the program file imports from `<pkg>` at all, relatively or absolutely;
  4. the program file's first line isn't a shebang whose flags include `-I` and `-S`.
- **The `-IS` run**, in the smoke-test step: copy the program file alone into a temporary folder and run
  `uv run python -IS "$tmp/<pkg>.py" --version`; the output starts with `<project> <pyproject version>`. This
  catches what the static check can't see: code that only works from inside `src/` or the virtualenv, and
  a standard-library module the interpreter doesn't actually ship.
- **Dev tools stay dev dependencies:** pytest, pytest-cov, ruff and mypy in `[dependency-groups] dev`;
  `uv sync`, `uv.lock` and `uv lock --check` unchanged. They never run in the installed program.

### Every template-owned file that changes

| File | For `stdlib-cli` |
|---|---|
| `copier.yml` | the `kind` choice; `has_cli`, `stdlib_only`; `container_image` and `integration_extras` not asked |
| `.agents/stack.md` | map: `src/<pkg>/<pkg>.py` (the program: stdlib only, argparse, runs as `python3 -IS`); Conventions: "Standard library only: no runtime dependency, ever (CI fails); the program file imports nothing from its own package"; the Config and Errors lines above in place of `config.SETTINGS` and `typer.echo`; the Dependencies line becomes "dev only"; `check-stdlib.py` in the Definition of done |
| `docs/wiki/Release-Process.md` | the version line names the literal and `extra-files`; the interpose bullet is gated off |
| `.github/dependabot.yml` | no interpose ignore; the `uv` entry stays for dev dependencies; no docker entry (no image) |
| `docs/wiki/.standard.toml` | `docs_touched` watches `src/*/<pkg>.py`, not `config.py` and `cli.py` |
| `scripts/gen-wiki.py` | no `settings` or `cli` block (`BLOCKS = {}`, as for a library): it imports nothing from the package or Typer, so no mypy or ruff override is needed |
| `pyproject.toml` | `dependencies = []` with a comment naming this record; no `[tool.hatch.metadata]`; no `types-pyyaml`; the `[project.scripts]` target above |
| `release-please-config.json` | the `extra-files` entry |
| `scripts/checks.d/20-python.sh` | the literal-version check |
| `.github/workflows/stack-ci.yml` | `check-stdlib.py` and the `-IS` run; no generated-wiki check change (it still runs, and passes with no blocks) |
| `.github/workflows/python-tag-check.yml` | unchanged: a no-op without git-tag pins, as for a library |
| `README.md` | Quick Start: `uv tool install` for development, or copy `src/<pkg>/<pkg>.py` onto `PATH` as `<project>`; it needs only `python3` |
| `.claude/settings.json` | `uv run <project>` stays (gated on `has_cli`) |
| `src/<pkg>/cli.py`, `config.py`, `test_cli.py`, `test_config.py`, `contrib/<project>.example.yaml` | not rendered |
| `tests/conftest.py` | rendered (seeded): a minimal one (a `clean_env` fixture), so a project moving from `cli` keeps its own |
| `src/<pkg>/<pkg>.py`, `tests/unit/test_<pkg>.py` | rendered (seeded): the program, and its tests (`--version`, `--help`, an unknown argument exits 2, the `-IS` run through the shebang) |
| `__init__.py`, `__main__.py`, `test_version.py` | as above |
| Wiki pages (seeded): Security, Troubleshooting, Architecture-Internals' components, Testing-Guide's layout | the interpose and `_FILE` text gated off; the program file in the components table |
| Dockerfile, `.dockerignore`, `contrib/`, the health command ([0010](0010-health-command.md)) | not rendered: no image, no service |

Template tests: a `stdlib-cli` variant in the render matrix, running its Definition of done, plus asserts
that it renders no interpose, Typer or PyYAML, `dependencies = []`, and that `check-stdlib.py` fails a
render given a `requests` import, a sibling import in the program file, or a dependency line.

## Alternatives considered

- **A boolean, `stdlib_only`, asked for `cli` (and perhaps `library`).** Keeps `kind` as "what it is", but
  for `cli` it changes nearly every file `cli` renders (CLI, config, version, dependencies, gen-wiki), so it
  is a second skeleton behind a flag; it adds a question to every `cli` render and combinations to
  validate (`stdlib_only` with `container_image`). For a library it changes nothing that matters: a library
  already has `dependencies = []`, and `-IS` doesn't apply to code imported into someone else's
  interpreter. *Rejected* for the kind value; `stdlib_only` survives as a derived name, so a later
  extension reads the same conditions.
- **No change: each project works around the template**, as rootctl does. Every update merges against
  the workarounds, and `stack.md` keeps telling assistants the wrong conventions. *Rejected.*
- **Allowing `service`.** 0004 makes every service FastAPI on uvicorn. A stdlib HTTP server
  (`http.server`) would need its own skeleton, health wiring and OpenAPI story. *Rejected.*
- **Allowing `container_image`.** An image brings its own interpreter and a uv-built virtualenv, so the
  reasons for standard library only (the system interpreter, one file on a host) don't apply; the image
  would also need its own HEALTHCHECK and entry-point rules. A project that wants one is a `cli`.
  *Rejected.*
- **A small stdlib settings loader in the skeleton** (env and a TOML file, project-owned). It is the copy
  that drifts, which 0003 removed for `cli` and `service`; and a tool that runs as root should take
  nothing from a caller-controlled environment unless it decides to. *Rejected*: none, and a rule in
  `stack.md`.
- **Vendoring interpose into the program file.** Makes the file large and puts a template-owned engine in
  project-owned code, the problem 0003 solved. *Rejected.*
- **Generating CLI-Reference from the argparse parser** (`build_parser()` as a contract for gen-wiki).
  Possible, but every project that replaces argparse (rootctl already has) drops the markers anyway, and a
  contract on a project-owned file needs the same overrides this record removes. *Rejected* for now:
  hand-written; revisit if a second project wants it.
- **`importlib.metadata` with a fallback, or reading `pyproject.toml` at run time.** Neither exists for an
  installed single file. *Rejected* for the literal.
- **A version file generated at build** (hatch-vcs, a `_version.py`). A PyPI build plugin and a second
  file the program would have to import. *Rejected.*
- **The program as `cli.py`.** Keeps the familiar name, but the release asset and the installed program
  are named after the project, and rootctl's file is already `<pkg>.py`. *Rejected* (resolved question 2).

## Consequences

- **Copier questions:** one new `kind` choice; nothing else changes for `service`, `cli` or `library`
  renders, whose files must render byte for byte as before (the matrix checks it).
- **Release:** `feat:` in template-python, a minor release. Not breaking.
- **`stack.md` budget:** the `stdlib-cli` render is shorter than `service` with an image (no `config` or
  Typer lines, no Dockerfile or contrib rows), so it stays inside the 6,750-character limit; the budget test
  is the check.
- **template-container:** nothing changes. It refuses to apply unless the stack answered
  `container_image: true`, which a `stdlib-cli` project never does, and it reads `kind` only for images.
- **Migration for rootctl:** `copier update --trust --data kind=stdlib-cli` in one PR. `src/**` is
  `_skip_if_exists`, so its own `src/rootctl/rootctl.py` is kept as it is (it already is the program file
  this record names, with the literal and its marker), and the deleted `cli.py` and `config.py` stay deleted
  (the new template no longer renders them). It then drops:
  1. the mypy override for `typer`, `rootctl.config` and `rootctl.cli`, and the ruff `known-first-party`
     block, both there only for gen-wiki;
  2. the sentence that its record wins over `stack.md`, which then describes it;
  3. its own stdlib-only import test, if `check-stdlib.py` covers it (it may keep it; it checks the same
     rule);
  and resolves two one-time merges: `release-please-config.json`'s `extra-files` (its plain string against
  the template's `{"type": "generic", ...}` object: take the template's) and `pyproject.toml`'s comment on
  `dependencies = []`. It keeps its hand parser, its coverage floor of 95, `install/` and its project-owned
  `release-assets.yml`. A new seeded test file (`tests/unit/test_rootctl.py`) is added only if absent; it
  keeps or deletes it.
- **Wiki pages:** Release-Process (template-owned) changes as above; the seeded pages change only for new
  projects.
- **Rollback:** remove the choice; a project on it moves back to `kind: cli` and its workarounds.
- **Follow-up, one `feat:` PR** after approval: `copier.yml`; the gates; the program, `__init__`,
  `__main__` and test skeletons; `check-stdlib.py`; `checks.d`, `stack-ci.yml`, `pyproject.toml`,
  `release-please-config.json`, `dependabot.yml`, `.standard.toml`, `gen-wiki.py`, `stack.md`, README and
  the wiki pages; the render-matrix variant and its tests; `docs/migrating/` for moving a `cli` project to
  `stdlib-cli`.

## Resolved questions

Approved by the brain coordinator for Stephen, 2026-11-04, with each open question answered as recommended.

1. **A kind value or a boolean?** A new kind, `kind: stdlib-cli`, with `stdlib_only` derived; not a
   `stdlib_only` question for `cli`. The flag would switch almost every `cli` file to a second skeleton,
   and it buys a library nothing.
2. **The name and the program file.** The kind is `stdlib-cli` (it says both what it is and the
   constraint) and the program file is `src/<pkg>/<pkg>.py` (the installed file is named after the program,
   and rootctl migrates without a rename).
3. **Configuration.** None in the skeleton, a rule in `stack.md` only. A project-owned loader is the
   drifting copy 0003 removed, and the right input for a strict tool is usually arguments only.
4. **Container images and services.** Neither: no `container_image` and no stdlib service for
   `stdlib-cli`. An image has its own interpreter, so the reason for the kind is gone; a service is FastAPI
   by 0004.
5. **Should the template publish the program file as a release asset?** No, not in this record. rootctl's
   assets are project-specific (its allowlist, sudoers file and installer) and already have their own
   workflow; two workflows uploading to one release would collide on the checksum file. Revisit when a
   second project needs it.
6. **How strict is the shebang check?** It requires `-I` and `-S` in the first line; the interpreter path
   is the project's (a non-Arch host, `/usr/local/bin/python3`). The kind's promise is `-IS`, not a path.

## Change log

| Date | Change |
|---|---|
| 2026-11-04 | The `-IS --version` smoke check matches a prefix: the first line starts with `<project> <version>`, then end of line or a space, so a program may add facts after them (approved by the brain coordinator for Stephen) |
| 2026-11-04 | `tests/conftest.py` has been rendered for `stdlib-cli` since v2.5.1 (a minimal one, so `copier update --data kind=stdlib-cli` keeps a project's own); the file table said not rendered and now matches |
