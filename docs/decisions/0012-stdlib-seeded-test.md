# 0012: A stdlib-cli seeded test that fits real programs

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Approved (2026-11-04)
Date: 2026-11-04
Authors: Stephen Cox

## Context

[0011](0011-stdlib-cli-kind.md) seeds `tests/unit/test_<pkg>.py` for `kind: stdlib-cli` (v2.5.1): `--version`
starts with `<project> X.Y.Z`, `--help` exits 0, an unknown option exits 2, and the program file copied
alone into `tmp_path` runs through its shebang's flags (`subprocess.run([interpreter, "-IS", copy,
"--version"])`). It calls the program as `main(argv)` and runs the copy with `subprocess.run`.

Both programs migrated so far failed it, and both deleted it:

- **andronics/rootctl** (an allowlisted root wrapper) failed two of the four tests.
  - *The usage error.* `main(["--no-such-option"])` returned 4, not 2. rootctl's own design record gives
    its codes: 2 is "refused by the allowlist", 3 is "bad arguments" (`EXIT_BAD_ARGUMENTS = 3`), and 4 is
    "will not run", which covers a journal that can't take the entry it writes before it parses anything.
    `main` takes its journal as a keyword argument (`main(argv, *, journal=..., runner=...)`), so a bare
    `main(argv)` reaches the real journal. The test conftest points that at a socket that doesn't exist,
    so the call exits 4.
  - *The run alone.* The test conftest's autouse guard replaces `subprocess.run`, `Popen`, `call`,
    `check_call` and `check_output` so that no test can run sudo, pacman or systemctl; the seeded test met
    the guard. rootctl already has a `real_popen` fixture for the tests that run a copy of a file on
    purpose.
- **andronics/passfill** failed the run alone the same way. Its guard records each refusal and fails the
    test again at teardown. Its usage error exits 2, so that test passed.
- **passfill's own test of `release-please-config.json`** failed too: it checked
  `"src/passfill/passfill.py" in config["packages"]["."]["extra-files"]`, and the migration had replaced
  the plain string with the template's `{"type": "generic", "path": ...}` object. The migration guide
  (docs/migrating/stdlib-cli.md) says to take the object; it doesn't say that a test reading the entry
  breaks.

The failures are quoted from the two migrations' test runs (v2.5.1, 2026-11-04).

Two facts shape the fix. Both were checked with a scratch render of this repository at v2.5.1 (pytest 9.2.0,
Python 3.13; the case numbers below are that experiment's):

- **A deleted seeded test comes back on every update.** `tests/**` is `_skip_if_exists`, which skips a
  file only while it exists. A render at v2.5.0, with `tests/unit/test_demo.py` deleted and committed,
  got the file back from `copier update` to v2.5.1. Deleting it is a chore on every update, not a one-off.
- **How pytest picks a fixture.** The closest definition of a name wins: one in the test module beats one
  in any conftest, and a conftest beats a plugin.
  - A default runner defined as a fixture in the seeded file can't be replaced by the project's conftest
    (case 01).
  - A default in the seeded `tests/conftest.py` reaches new projects only: an existing project keeps its
    own conftest, and the seeded test then errors with "fixture not found" (case 06).
  - A default in a plugin, or none at all with the test looking the fixture up by name, lets the
    project's conftest win (cases 02, 07, 08).
  - `subprocess.run` looks `Popen` up in the `subprocess` module each time it is called. A project
    override that returns a `run` it saved before its guard still meets the guard, because the guard
    replaced `Popen` (cases 02 and 07, first run). An override must be built on the saved `Popen`, as
    rootctl's `real_popen` is.

## Decision

### The usage-error code comes from the program

- The program file may declare `EXIT_USAGE` (an `int`): the code it exits with on a usage error. The
  skeleton declares `EXIT_USAGE = 2` beside its parser, with the comment "argparse's code; a parser of the
  project's own names its own here".
- The seeded test reads `getattr(program, "EXIT_USAGE", 2)`, so a program without the constant is held to
  2 as today. Its test is renamed `test_an_unknown_option_exits_with_the_usage_code`. A hand parser that
  exits 3 passes with `EXIT_USAGE = 3` and fails without it (exit-code cases).
- The rule, for `stdlib-cli` only: "a usage error is one line and exits with `EXIT_USAGE` (2 unless the
  program declares another, and the project's design record says why)". This replaces 0011's "an unknown
  argument exits 2" (its table of changed files) and the stdlib-cli Errors line in `.agents/stack.md`.
  0011's sentence that argparse exits 2, "matching the template's 'one line, exit 2' rule", stays true for
  the skeleton. `cli` and `service` keep "exit 2": Typer sets it, and nothing has asked for another.
- rootctl adds `EXIT_USAGE = EXIT_BAD_ARGUMENTS`.

### The seeded test calls the program through two fixtures a project may supply

- `stdlib_cli_main`: a callable `(argv: list[str]) -> int`. The default is today's `exit_code`: `main(argv)`,
  with a `SystemExit` turned into its code. It is used for `--version`, `--help` and the usage error.
- `stdlib_cli_run`: a callable `(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]`. The
  default is `subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)`. It is used for
  the run alone.
- The seeded file asks for each one with `request.getfixturevalue(name)`, and on
  `pytest.FixtureLookupError` uses its own default, written as a plain function and not as a fixture. So
  a project with neither fixture runs exactly as today, and a project that defines one in any conftest
  gets its own (case 02). Everything stays in the one seeded file: no plugin, and no `pyproject.toml`
  change.
- The file's docstring says when to supply them: when the conftest guards `subprocess` (build
  `stdlib_cli_run` on the `Popen` saved before the guard), or when `main` takes dependencies it must be
  given in tests (rootctl's journal). The migration guide shows both, at about eight lines each.
- rootctl supplies both: `stdlib_cli_main` passes its fake journal, and `stdlib_cli_run` uses
  `real_popen`. passfill supplies `stdlib_cli_run` only.

### Seeded on copy only

- `_exclude` gains `tests/unit/test_<pkg>.py` when `_copier_operation != 'copy'`, as `test_hello.py`
  already is. A new project gets it on `copier copy` and keeps it from then on: neither side of an update
  has it, so the update leaves it alone. A project that moves to `stdlib-cli`, which arrives with tests of
  its own, isn't handed it, and a project that deletes it doesn't get it back.

### The migration guide

`docs/migrating/stdlib-cli.md` changes in two places:

- Step 2, under `release-please-config.json`, gets this line: "A test of the project's own that reads this
  entry (for instance `"src/<package>/<package>.py" in config["packages"]["."]["extra-files"]`) now finds
  an object: match the entry's `path`."
- Step 4 no longer says the seeded test "holds for any parser". It says the update doesn't add the file,
  and that to use it, the project takes it from a fresh render, declares `EXIT_USAGE` if its usage code
  isn't 2, and supplies `stdlib_cli_main` and `stdlib_cli_run` if its conftest guards `subprocess` or
  `main` needs dependencies injected. It shows both overrides.

## Alternatives considered

- **Do nothing; document deleting the file.** It costs nothing in the template, but an update re-adds the
  file every time (see Context), so each project deletes it again after every update, and the guide's
  line would have to say so. *Rejected*. Copy-only seeding, above, keeps the cheap part: a project that
  doesn't want the file never has to delete it twice.
- **Slim the seeded test to `--version` and `--help`**, dropping the usage error and the run alone (CI's
  smoke step already runs the file alone with `python -IS`). Both programs would keep it unchanged. But
  the usage rule would then have no test anywhere, and the shebang's own interpreter would never run (CI
  uses uv's Python). *Not chosen*: it is the fallback in open question 1.
- **A default fixture in the seeded test module.** The project's conftest can't replace it (case 01).
  *Rejected.*
- **A default fixture in the seeded `tests/conftest.py`.** It reaches only projects created after the
  change. An existing project's own conftest is kept, and the test errors with "fixture not found"
  (case 06). *Rejected.*
- **A default fixture in a template-owned pytest plugin** (`-p` in the merged `pyproject.toml` addopts,
  with `pythonpath`). It works (cases 07, 08), but it adds a file and two pytest settings to every
  `stdlib-cli` project for one test file. *Rejected* in favour of the lookup, which works the same way.
- **Bind the real `Popen` when the test module is imported.** It passes a guard that patches in a fixture
  (case 12), because it walks past that guard without a word. A guard is there on purpose, so passing it
  should be the project's explicit choice. *Rejected.*
- **A marker the guard honours** (`@pytest.mark.real_subprocess`). Every project's guard would have to
  read it, and a guard that doesn't still fails. That is a contract on project code with no fallback, the
  kind 0011 turned down for gen-wiki. *Rejected.*
- **The usage code as a fixture rather than a constant.** The code is a fact about the program, not about
  the test environment, and a constant sits next to the parser that produces it. *Rejected.*

## Consequences

- **What reaches existing projects.** `.agents/stack.md` and the guide are template-owned and arrive on
  the next update. The seeded test does not: `tests/**` is the project's, and with copy-only seeding an
  update neither adds it nor touches it. rootctl and passfill deleted theirs. To have one, each takes it
  from a fresh render and adds the overrides above; that is optional. A project that kept the v2.5.x file
  keeps it unchanged (it passed there), and an update stops re-adding it once deleted.
- **New projects** get the new file. Its defaults behave exactly as today's for the argparse skeleton.
- **0011** is partly superseded: its seeded-test row ("an unknown argument exits 2")
  and the stack.md Errors line it lists for `stdlib-cli`. Everything else in it stands. It carries a
  pointer line to this record.
- **Release:** `fix:` in template-python, a patch release. No project breaks and nothing new is asked;
  `EXIT_USAGE` and both fixtures are optional.
- **Template tests**, in the `stdlib-cli` variant:
  - a rootctl-like hand parser that exits 3 passes with `EXIT_USAGE = 3`;
  - a conftest guard that replaces `subprocess`, with a `stdlib_cli_run` built on the saved `Popen`,
    passes;
  - a `stdlib_cli_main` override is used;
  - `copier update` doesn't add `tests/unit/test_<pkg>.py`, and leaves a new project's copy alone.
  The `service`, `cli` and `library` renders stay byte for byte the same.
- **Rollback:** restore the v2.5.1 seeded file and drop the `_exclude` line. A program's `EXIT_USAGE` can
  stay; nothing else reads it.
- **Follow-up, one `fix:` PR** after approval:
  1. the seeded test, with the lookups and `EXIT_USAGE`;
  2. the skeleton's `EXIT_USAGE = 2`;
  3. the `_exclude` line;
  4. the stack.md Errors line for `stdlib-cli`;
  5. the guide's two changes;
  6. the template tests above.

## Resolved questions

Approved by the brain coordinator for Stephen, 2026-11-04, with each open question answered as recommended.

1. **Hooks and a constant, or a slimmer seeded test?** Hooks and a constant: `EXIT_USAGE`, plus the
   `stdlib_cli_main` and `stdlib_cli_run` fixtures looked up by name. It keeps the usage check and the
   shebang run wherever a program can meet them, at three short additions for rootctl and one for passfill.
2. **Seed the file on copy only, or on every update as now?** Copy only, as `test_hello.py` is. Migrating
   projects arrive with tests of their own, and a deletion should last; a new project still gets the file.
3. **The constant's name, and whether the skeleton declares it.** `EXIT_USAGE`, declared in the skeleton as
   `EXIT_USAGE = 2`. Whoever replaces the parser sees the constant beside it, and `EXIT_` matches the names
   rootctl already uses.
4. **Should CI check `EXIT_USAGE`?** No. The seeded test is the check wherever the file is kept; another
   rule in `check-stdlib.py` would be one more contract on project code, for a constant only that test reads.
5. **Does `kind: cli` (and `service`) keep "one line, exit 2"?** Yes, unchanged. Typer fixes the code at 2
   for those kinds, and no project has asked for another.
6. **Release type.** `fix:`, a patch release. Nothing breaks and nothing new is asked: it repairs a seeded
   file that didn't fit real programs.
