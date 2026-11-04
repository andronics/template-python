# Moving a `cli` project to `stdlib-cli`

For a `kind: cli` project that must import nothing from PyPI and run as `python3 -IS`: template-python's
decision [0011](../decisions/0011-stdlib-cli-kind.md). The first is andronics/rootctl, which was rendered as
`cli` (v2.4.4) and then took the CLI apart by hand; its migration is the worked example below. Paste
everything below the line into a Claude Code session opened in that project.

---

Move this project from `kind: cli` to `kind: stdlib-cli`, as template-python's decision 0011 describes: one
program module, `src/<package>/<package>.py`, standard library only, run as `python3 -IS`. Work on a branch
and open one PR; don't push to `main`.

## 1. Know what changes

Read decision 0011 first (template-python's `docs/decisions/0011-stdlib-cli-kind.md`): its table lists every
template-owned file that changes. In short, after the update:

- `pyproject.toml` has `dependencies = []`, no `[tool.hatch.metadata]`, no `types-pyyaml`, and
  `[project.scripts]` `<project> = "<package>.<package>:main"`;
- `release-please-config.json` lists `src/<package>/<package>.py` in `extra-files`, and
  `scripts/checks.d/20-python.sh` checks its literal `__version__` against `pyproject.toml`;
- `scripts/check-stdlib.py` is new, and `stack-ci.yml` runs it on every supported Python, and runs the
  program file alone with `python -IS --version`: the first line must start with `<project> X.Y.Z`, then
  end of line or a space, so a tail of the program's own (`rootctl 0.1.0 (python 3.13.15, ...)`) passes;
- `scripts/gen-wiki.py` has no `settings` or `cli` block; `.agents/stack.md`, `dependabot.yml`,
  `docs/wiki/.standard.toml` and `docs/wiki/Release-Process.md` describe the new shape.

`src/**`, `tests/**` and the seeded wiki pages are this project's (`_skip_if_exists`): the update never
rewrites them, so steps 3 to 5 are yours.

## 2. Take the update with the new kind

```sh
uvx copier update --trust --defaults --skip-tasks -a .copier-answers.stack-python.yml --data kind=stdlib-cli
```

A project with an image can't move: `stdlib-cli` never has `container_image` (an image brings its own
interpreter, so the reason for the kind is gone). Stay a `cli`.

Resolve each conflict:

- **`release-please-config.json`**: take the template's `{"type": "generic", "path": "src/<package>/<package>.py"}`
  over a plain string entry.
- **`pyproject.toml`**: keep the template's comment on `dependencies = []`; keep the project's own
  additions (a coverage floor above 80, extra ruff rules) and drop what was only there for the old CLI.
- The files the template no longer renders (`src/<package>/cli.py`, `src/<package>/config.py`,
  `tests/unit/test_cli.py`, `tests/unit/test_config.py`, `contrib/<project>.example.yaml`): the update
  deletes them, project edits and all, without a conflict. If one held something step 3 needs, take it
  back from the last commit (`git show HEAD:<path>`) and move it into the program file or a test of the
  project's own; otherwise leave it deleted.
- `tests/conftest.py` is kept as it is: `stdlib-cli` seeds one too, so the project's own fixtures survive.
  Drop what imports `<package>.config`, which is gone.

Then `sh scripts/post-update.sh` (it refreshes `uv.lock`: interpose, Typer and PyYAML leave it).

## 3. Make the program file

- `src/<package>/<package>.py` is the whole program: parsing, `main()` and everything it calls. If the code
  is spread over several modules, merge it into this one: a file run by path under `-I` can't import its
  siblings. (Splitting it again, into a zipapp built at release, is its own design record.)
- Its first line is `#!/usr/bin/python3 -IS` (another interpreter path is fine; the flags must include
  `-I` and `-S`).
- It imports only the standard library and nothing from `<package>`.
- `__version__ = "X.Y.Z"  # x-release-please-version`, with `pyproject.toml`'s current version: a literal,
  since an installed single file has no package metadata.
- `main(argv=None) -> int`. The template's skeleton uses argparse with `allow_abbrev=False`; a project
  with its own parser keeps it (nothing template-owned imports the parser).
  `--version`'s first line starts with `<project> X.Y.Z`; the program may add its own facts after a space. Write output with `sys.stdout.write` and `sys.stderr.write`, and
  exit 2 on a usage error.
- Configuration: arguments first. If it needs more, environment variables named `<PREFIX><KEY>`, read in
  one place, and a file, if any, is TOML read with `tomllib`; write the precedence on the wiki's
  In-Depth-Configuration page.
- `__init__.py` re-exports `__version__` from it (`from <package>.<package> import __version__`);
  `__main__.py` is `sys.exit(main())` from it. Neither is needed by the installed file.

A new project's skeleton shows the finished shape: render `uvx copier copy` of template-base and
template-python with `kind=stdlib-cli` into a scratch folder and read its `src/` and `tests/`.

## 4. Tests

- `tests/unit/test_<package>.py`: `--version`'s first line starts with `<project> X.Y.Z` (alone or
  followed by a space), `--help` exits 0, an unknown option exits 2, and the file copied alone into
  `tmp_path` runs with its shebang's flags. The skeleton's tests only that, through `main` and
  `__version__`, so it holds for any parser: add it if the project has none. Test the commands in files
  of their own.
- `tests/unit/test_version.py`: drop the `0+unknown` alternative; the literal is always a real version.
- A test of the project's own that the program imports only the standard library may stay, or go:
  `scripts/check-stdlib.py` checks the same rule.

## 5. Docs and leftovers

- The wiki: CLI-Reference is hand-written now (no `<!-- generated:start cli -->` block), and
  In-Depth-Configuration has no `settings` block: `gen-wiki.py` fails on a block it doesn't know. Remove
  both markers and write the content. Security and Troubleshooting lose their `_FILE` and `config`
  command text; Architecture-Internals' components table names the program file.
- Drop each workaround the old `cli` render needed: a mypy override (`ignore_missing_imports` for `typer`,
  `<package>.config`, `<package>.cli`) and a ruff `known-first-party` block that were there only for
  `gen-wiki.py`; a sentence saying the project's own record wins over `.agents/stack.md` where they
  differ, which `stack.md` now describes.
- Keep what is the project's: release assets and their workflow, install scripts, its coverage floor.

## 6. Check

```sh
sh scripts/checks.sh
uv sync --locked && uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
uv run scripts/gen-wiki.py --check
uv run scripts/check-stdlib.py
tmp=$(mktemp -d) && cp src/<package>/<package>.py "$tmp/" && uv run python -IS "$tmp/<package>.py" --version
```

Commit as `refactor: move to template-python's stdlib-cli kind (0011)` (`feat:` if a command or its output
changed) and open the PR. In its body, list the files deleted, the workarounds dropped and any conflict
resolved by hand.

## rootctl

`src/rootctl/rootctl.py` already is the program file, with the literal and its marker, and `cli.py` and
`config.py` are already deleted, so the update keeps both as they are. It drops the mypy override and the
`known-first-party` block (step 5), and the sentence in its design record that its record wins over
`stack.md`. Its `--version` tail (`rootctl 0.1.0 (python 3.13.15, isolated=1, no_site=1)`), which its
installer reads, stays: CI's check matches the start of the line. Its `tests/conftest.py` stays. Its own stdlib-only import test may stay. The two one-time merges are `release-please-config.json`'s
`extra-files` (take the template's object) and the comment on `dependencies = []`. It keeps its hand
parser, its coverage floor of 95, `install/` and its project-owned `release-assets.yml`. The new
`tests/unit/test_rootctl.py` is added only if absent: keep or delete it.
