"""Decision 0011: `kind: stdlib-cli`, a command that imports nothing from PyPI and runs as `python3 -IS`.

The render matrix's `stdlib-cli` variant runs its Definition of done (test_python.py, with
scripts/check-stdlib.py); these tests pin what is particular to it.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import textwrap
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from conftest import render
from stacking import ROOT, checks, commit, sh
from test_python import run, update

STDLIB = pytest.mark.parametrize("variant", ["stdlib-cli"], indirect=True)
PROGRAM = "src/demo/demo.py"
NOT_RENDERED = ["src/demo/cli.py", "src/demo/config.py", "tests/unit/test_cli.py",
                "tests/unit/test_config.py", "contrib/demo.example.yaml", "Dockerfile", ".dockerignore",
                "docker", "contrib/systemd", "docs/wiki/Deployment.md", "docs/openapi.json"]  # fmt: skip


@STDLIB
def test_renders_the_program_and_none_of_typer_or_interpose(project: Path) -> None:
    for path in NOT_RENDERED:
        assert not (project / path).exists(), path
    for path in (PROGRAM, "src/demo/__init__.py", "src/demo/__main__.py", "tests/conftest.py",
                 "tests/unit/test_demo.py", "tests/unit/test_hello.py", "scripts/check-stdlib.py"):  # fmt: skip
        assert (project / path).is_file(), path
    assert (project / PROGRAM).read_text().startswith("#!/usr/bin/python3 -IS\n")
    assert '__version__ = "0.0.0"  # x-release-please-version\n' in (project / PROGRAM).read_text()
    assert "\nEXIT_USAGE = 2  # argparse's code; a parser of the project's own names its own here\n" in (
        project / PROGRAM).read_text()  # fmt: skip
    # No interpose, Typer or PyYAML anywhere they would be installed, imported or documented.
    looked = [project / p for p in ("pyproject.toml", "uv.lock", ".agents/stack.md", ".github/dependabot.yml")]
    looked += [p for d in ("src", "tests", "scripts", "docs/wiki") for p in (project / d).rglob("*") if p.is_file()]
    for path in looked:
        text = path.read_text().lower()
        for name in ("interpose", "typer", "pyyaml", "import yaml"):
            assert name not in text, f"{path.relative_to(project)} names {name}"


# A program with its own parser and a tail on its version line, as andronics/rootctl's: the seeded
# test and CI's smoke step hold for it too (they need only `main`, `__version__` and the file).
HAND_PARSER = '''#!/usr/bin/python3 -IS
"""A demo project, with a hand parser."""

from __future__ import annotations

import platform
import sys
from collections.abc import Sequence

__version__ = "0.0.0"  # x-release-please-version

USAGE = "usage: demo [--help] [--version]\\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--help"]:
        sys.stdout.write(USAGE)
        return 0
    if args == ["--version"]:
        f = sys.flags
        tail = f"python {platform.python_version()}, isolated={f.isolated}, no_site={f.no_site}"
        sys.stdout.write(f"demo {__version__} ({tail})\\n")
        return 0
    sys.stderr.write(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main())
'''
# --version's output, and whether CI's smoke step takes it: the first line starts with
# "demo 0.0.0", alone or followed by a space.
VERSION_LINES = {"demo 0.0.0": True, "demo 0.0.0 (python 3.13.15, isolated=1, no_site=1)": True,
                 "demo 0.0.0\nmore lines": True, "demo 0.0.01": False, "demo 0.0.0-dev": False,
                 "demo": False, "other 0.0.0": False}  # fmt: skip


def prints_version(line: str, dst: Path) -> Path:
    """A copy of the program whose --version prints `line`."""
    text = HAND_PARSER.replace('f"demo {__version__} ({tail})\\n"', repr(line + "\n"))
    dst.mkdir(parents=True)
    (dst / "demo.py").write_text(text)
    return dst / "demo.py"


@STDLIB
def test_pyproject(project: Path) -> None:
    text = (project / "pyproject.toml").read_text()
    pyproject = tomllib.loads(text)
    assert pyproject["project"]["dependencies"] == []
    assert "dependencies = []\n" in text and "decision 0011" in text.split("dependencies = []")[0]
    assert "optional-dependencies" not in pyproject["project"]
    assert pyproject["project"]["scripts"] == {"demo": "demo.demo:main"}
    assert "hatch" not in pyproject["tool"] or "metadata" not in pyproject["tool"]["hatch"]
    assert "types-pyyaml" not in pyproject["dependency-groups"]["dev"]
    # Only the dev tools are locked.
    locked = {p["name"] for p in tomllib.loads((project / "uv.lock").read_text())["package"]}
    assert {"mypy", "pytest", "ruff"} <= locked and not locked & {"typer", "pyyaml", "interpose", "click"}


@STDLIB
def test_template_owned_files(project: Path) -> None:
    config = json.loads((project / "release-please-config.json").read_text())
    assert config["packages"]["."]["extra-files"] == [{"type": "generic", "path": PROGRAM}]
    dependabot = yaml.safe_load((project / ".github/dependabot.yml").read_text())
    assert [(u["package-ecosystem"], "ignore" in u) for u in dependabot["updates"]] == [
        ("github-actions", False), ("uv", False)]  # fmt: skip
    standard = tomllib.loads((project / "docs/wiki/.standard.toml").read_text())
    assert "src/*/demo.py" in standard["docs_touched"]["watch"]
    assert not {"src/*/config.py", "src/*/cli.py"} & set(standard["docs_touched"]["watch"])
    assert "BLOCKS: dict[str, Callable[..., str]] = {}\n" in (project / "scripts/gen-wiki.py").read_text()
    stack = (project / ".agents/stack.md").read_text()
    assert "`uv run scripts/check-stdlib.py`" in stack and "**Standard library only:**" in stack
    assert "config.SETTINGS" not in stack and "typer" not in stack.lower()
    assert "a usage error is one line and exits with `EXIT_USAGE` (2 unless" in stack and "exit 2" not in stack
    release = (project / "docs/wiki/Release-Process.md").read_text()
    assert "`extra-files`" in release and "**interpose**" not in release
    assert "Bash(uv run demo:*)" in json.loads((project / ".claude/settings.json").read_text())["permissions"]["allow"]


@STDLIB
def test_ci_runs_the_check_and_the_file_alone(project: Path, tmp_path: Path) -> None:
    """stack-ci.yml's test matrix runs check-stdlib.py, and its smoke step runs the program file
    alone with `python -IS`: run that step as CI does. --version's first line must start with
    `demo 0.0.0`, alone or followed by a space (a program may add its own tail)."""
    steps = yaml.safe_load((project / ".github/workflows/stack-ci.yml").read_text())["jobs"]["test"]["steps"]
    assert "uv run scripts/check-stdlib.py" in [s.get("run") for s in steps]
    smoke = next(s["run"] for s in steps if s.get("name") == "Import and entry-point smoke test")
    assert 'uv run python -IS "$tmp/demo.py" --version' in smoke
    result = run(project, "bash", "-euo", "pipefail", "-c", smoke)
    assert result.returncode == 0, result.stdout + result.stderr
    for i, (line, ok) in enumerate(VERSION_LINES.items()):
        program = prints_version(line, tmp_path / str(i))
        result = run(project, "bash", "-euo", "pipefail", "-c", smoke.replace(f"cp {PROGRAM} ", f"cp {program} "))
        assert (result.returncode == 0) is ok, (line, result.stdout + result.stderr)
        if not ok:
            assert f"--version printed '{line.splitlines()[0]}': its first line must be 'demo 0.0.0'" in result.stdout


@STDLIB
def test_runs_alone_as_python_IS(project: Path, tmp_path: Path) -> None:
    """The file alone runs under -IS; beside a sibling module it still can't import it (-I implies -P)."""
    alone = Path(shutil.copy(project / PROGRAM, tmp_path / "demo.py"))
    result = subprocess.run([sys.executable, "-IS", str(alone), "--version"], capture_output=True, text=True)
    assert (result.returncode, result.stdout) == (0, "demo 0.0.0\n"), result.stderr
    (tmp_path / "helper.py").write_text("")
    alone.write_text(alone.read_text().replace("import sys\n", "import sys\n\nimport helper\n", 1))
    result = subprocess.run([sys.executable, "-IS", str(alone), "--version"], capture_output=True, text=True)
    assert result.returncode != 0 and "No module named 'helper'" in result.stderr


@STDLIB
def test_seeded_tests_hold_for_a_hand_parser(project: Path, tmp_path: Path) -> None:
    """tests/unit/test_demo.py tests only what every stdlib-cli program has, so it passes for a
    program with its own parser and a tail on its version line; the skeleton's own pass it too."""
    dst = tmp_path / "p"
    shutil.copytree(project, dst, symlinks=True, ignore=shutil.ignore_patterns(".git", ".venv"))
    (dst / PROGRAM).write_text(HAND_PARSER)
    for where in (project, dst):
        result = run(where, "uv", "run", "pytest", "tests/unit/test_demo.py", "--no-cov", "-p", "no:cacheprovider")
        assert result.returncode == 0 and "4 passed" in result.stdout, result.stdout + result.stderr
    # The example command's test is a file of its own, to delete with it.
    assert "hello" not in (project / "tests/unit/test_demo.py").read_text()
    assert "delete this file along with `hello`" in (project / "tests/unit/test_hello.py").read_text()


def guide_example(fixture: str) -> str:
    """docs/migrating/stdlib-cli.md's example of a conftest's `fixture`, so the guide's code is tested."""
    guide = (ROOT / "docs/migrating/stdlib-cli.md").read_text()
    blocks = [textwrap.dedent(b) for b in re.findall(r"```python\n(.*?)\n *```", guide, re.DOTALL)]
    found = [b for b in blocks if f"def {fixture}(" in b]
    assert len(found) == 1, f"the guide shows {fixture} {len(found)} times"
    return found[0] + "\n"


# A conftest guard, as andronics/rootctl's and passfill's: no test runs a process.
GUARD = """
import subprocess
from collections.abc import Callable
from pathlib import Path

REAL_RUN = subprocess.run


@pytest.fixture(autouse=True)
def no_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("refused: a test ran a process")

    for name in ("run", "Popen", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, refuse)

"""
# A run built on the `run` saved before the guard: it still meets the guard (decision 0012).
RUN_ON_SAVED_RUN = """
@pytest.fixture
def stdlib_cli_run() -> Callable[[list[str], Path], subprocess.CompletedProcess[str]]:
    return lambda argv, cwd: REAL_RUN(argv, cwd=cwd, capture_output=True, text=True, check=False)
"""
# A main that needs a journal it must be given in tests, as rootctl's: without one it exits 4
# before it parses anything, because the conftest points the real one at a path that doesn't exist.
NEEDS_A_JOURNAL = [
    ("import sys\n", "import os\nimport sys\n"),
    ("def main(argv: Sequence[str] | None = None) -> int:\n",
     ('JOURNAL = "/dev/null"\n\n\ndef main(argv: Sequence[str] | None = None, *, journal: str | None = None) -> int:\n'
      '    if not os.path.exists(journal or JOURNAL):\n        return 4\n')),
]  # fmt: skip
JOURNAL = """
from collections.abc import Callable
from pathlib import Path

from demo import demo as program
from demo.demo import main


@pytest.fixture(autouse=True)
def no_real_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(program, "JOURNAL", "/no/such/journal.sock")


def FakeJournal(path: Path) -> str:
    path.touch()
    return str(path)

"""
# Each case: the program file (None: the skeleton's), what the conftest gains, and pytest's summary.
SEEDED: dict[str, tuple[str | None, str, str]] = {
    "the skeleton": (None, "", "4 passed"),
    "a hand parser exiting 3, declared": (
        HAND_PARSER.replace("    return 2\n", "    return 3\n").replace("USAGE = ", "EXIT_USAGE = 3\nUSAGE = "), "",
        "4 passed"),
    "a hand parser exiting 3, undeclared": (HAND_PARSER.replace("    return 2\n", "    return 3\n"), "",
                                            "1 failed, 3 passed"),
    "a guard, no stdlib_cli_run": (None, GUARD, "1 failed, 3 passed"),
    "a guard, stdlib_cli_run on the saved Popen": (None, GUARD + "GUIDE:stdlib_cli_run", "4 passed"),
    "a guard, stdlib_cli_run on the saved run": (None, GUARD + RUN_ON_SAVED_RUN, "1 failed, 3 passed"),
    "a journal, no stdlib_cli_main": ("JOURNAL", JOURNAL, "3 failed, 1 passed"),
    "a journal, stdlib_cli_main": ("JOURNAL", JOURNAL + "GUIDE:stdlib_cli_main", "4 passed"),
}  # fmt: skip


@STDLIB
@pytest.mark.parametrize("case", SEEDED)
def test_seeded_test_fits_the_program(case: str, project: Path, tmp_path: Path) -> None:
    """tests/unit/test_demo.py (decision 0012): the usage code is the program's EXIT_USAGE (2 if
    undeclared), and a conftest's `stdlib_cli_main` and `stdlib_cli_run`, as the migration guide
    shows them, are used in place of the file's defaults; without them it runs as before."""
    program, extra, summary = SEEDED[case]
    dst = tmp_path / "p"
    shutil.copytree(project, dst, symlinks=True, ignore=shutil.ignore_patterns(".git", ".venv"))
    if program == "JOURNAL":
        for old, new in NEEDS_A_JOURNAL:
            edit(PROGRAM, old, new)(dst)
    elif program is not None:
        (dst / PROGRAM).write_text(program)
    for fixture in ("stdlib_cli_run", "stdlib_cli_main"):
        extra = extra.replace(f"GUIDE:{fixture}", guide_example(fixture))
    append("tests/conftest.py", extra)(dst)
    result = run(dst, "uv", "run", "pytest", "tests/unit/test_demo.py", "--no-cov", "-p", "no:cacheprovider")
    assert re.search(rf"^(=+ )?{re.escape(summary)} in ", result.stdout, re.MULTILINE), result.stdout + result.stderr
    if "failed" in summary and "journal" not in case:
        failed = "test_an_unknown_option" if "parser" in case else "test_runs_alone_through_its_shebang"
        assert f"FAILED tests/unit/test_demo.py::{failed}" in result.stdout, result.stdout


def test_update_from_cli_keeps_the_projects_tests(base_src: Path, python_src: Path, tmp_path: Path) -> None:
    """`copier update --data kind=stdlib-cli` on a cli project: a project-owned file the new kind
    doesn't render is deleted, edits and all, without a conflict. stdlib-cli renders a seeded
    tests/conftest.py, so the project's own (`_skip_if_exists`) is kept; the cli-only files
    (Typer, interpose) go, as docs/migrating/stdlib-cli.md says."""
    project = render(base_src, python_src, tmp_path / "p", kind="cli", container_image=False)
    with (project / "tests/conftest.py").open("a") as f:
        f.write("\n# the project's own fixture\n")
    commit(project)
    sh("uvx", "--from", "copier>=9.19,<10", "copier", "update", "-a", ".copier-answers.stack-python.yml", "--trust",
       "--skip-tasks", "--defaults", "--conflict", "inline", "--vcs-ref", "v1.0.0", "--data", "kind=stdlib-cli",
       cwd=project)  # fmt: skip
    conftest = (project / "tests/conftest.py").read_text()
    assert "# the project's own fixture\n" in conftest and "from demo.config import ENV_PREFIX" in conftest
    assert "<<<<<<<" not in conftest
    status = sh("git", "status", "--porcelain", cwd=project).splitlines()
    deleted = sorted(line[3:] for line in status if line.startswith(" D"))
    assert deleted == ["contrib/demo.example.yaml", "src/demo/cli.py", "src/demo/config.py",
                       "tests/unit/test_cli.py", "tests/unit/test_config.py"], status  # fmt: skip
    assert "tests/conftest.py" not in "\n".join(status)
    # The seeded tests are for new projects only (decision 0012): the project brings its own.
    assert not (project / "tests/unit/test_demo.py").exists() and not (project / "tests/unit/test_hello.py").exists()


SEEDED_ON_COPY = ["tests/unit/test_hello.py", "tests/unit/test_demo.py"]


def test_update_keeps_the_seeded_tests(base_src: Path, python_src: Path, tmp_path: Path) -> None:
    """tests/unit/test_hello.py and test_demo.py are rendered on copy only (`_exclude` on update,
    decision 0012): an update leaves a new project's copies, edits and all."""
    project = render(base_src, python_src, tmp_path / "p", kind="stdlib-cli")
    for path in SEEDED_ON_COPY:
        with (project / path).open("a") as f:
            f.write("# a project edit\n")
    commit(project)
    update(project, "v1.0.0")
    assert sh("git", "status", "--porcelain", cwd=project) == ""
    for path in SEEDED_ON_COPY:
        assert "# a project edit\n" in (project / path).read_text(), path


def test_update_doesnt_bring_back_a_deleted_seeded_test(base_src: Path, python_src: Path, tmp_path: Path) -> None:
    """A project that deletes a seeded test keeps it deleted: `tests/**` is `_skip_if_exists`, which
    re-adds a missing file, so only `_exclude` keeps it out (decision 0012)."""
    project = render(base_src, python_src, tmp_path / "p", kind="stdlib-cli")
    sh("git", "rm", "-q", *SEEDED_ON_COPY, cwd=project)
    commit(project)
    update(project, "v1.0.0")
    assert sh("git", "status", "--porcelain", cwd=project) == ""
    for path in SEEDED_ON_COPY:
        assert not (project / path).exists(), path


def edit(path: str, old: str, new: str) -> Callable[[Path], None]:
    def change(project: Path) -> None:
        file = project / path
        text = file.read_text()
        assert old in text, (path, old)
        file.write_text(text.replace(old, new, 1))

    return change


def append(path: str, text: str) -> Callable[[Path], None]:
    def change(project: Path) -> None:
        with (project / path).open("a") as f:
            f.write(text)

    return change


IN_A_FUNCTION = "\n\ndef fetch() -> None:\n    import requests  # noqa: F401\n"
BREAKS: dict[str, tuple[Callable[[Path], None], str]] = {
    "requests import": (edit(PROGRAM, "import sys\n", "import sys\n\nimport requests\n"),
                        f"{PROGRAM}:14: imports requests, which isn't the standard library"),
    "requests import in a function": (append(PROGRAM, IN_A_FUNCTION), "imports requests, which isn't"),
    "requests import in another module": (append("src/demo/__init__.py", "import requests\n"),
                                          "src/demo/__init__.py:7: imports requests"),
    "sibling import": (edit(PROGRAM, "import sys\n", "import sys\n\nfrom demo import helper\n"),
                       "the program file imports from its own package (demo)"),
    "relative sibling import": (edit(PROGRAM, "import sys\n", "import sys\n\nfrom . import helper\n"),
                                "the program file imports from its own package"),
    "dynamic import": (append(PROGRAM, "\n__import__(sys.argv[0])\n"), "a dynamic import of a computed name"),
    "dynamic import of a package": (append(PROGRAM, '\nimportlib.import_module("requests")\n'),
                                    "a dynamic import of requests, not the standard library"),
    "dependency line": (edit("pyproject.toml", "dependencies = []", 'dependencies = ["requests>=2.32"]'),
                        "[project] dependencies must be empty (standard library only): requests>=2.32"),
    "optional dependencies": (append("pyproject.toml", '\n[project.optional-dependencies]\nhttp = ["requests"]\n'),
                              "[project.optional-dependencies] isn't allowed"),
    "shebang without -S": (edit(PROGRAM, "#!/usr/bin/python3 -IS", "#!/usr/bin/python3 -I"),
                           "the shebang's flags must include -I and -S (missing -S)"),
    "no shebang": (edit(PROGRAM, "#!/usr/bin/python3 -IS\n", ""), "the first line must be a python shebang"),
}  # fmt: skip
ALLOWED: dict[str, Callable[[Path], None]] = {
    "stdlib import in a function": append(PROGRAM, "\n\ndef dump() -> None:\n    import json  # noqa: F401\n"),
    "dynamic import of the stdlib": append(PROGRAM, '\n__import__("json")\n'),
    "another interpreter path": edit(PROGRAM, "#!/usr/bin/python3 -IS", "#!/usr/local/bin/python3 -I -S"),
}  # fmt: skip


def check_stdlib(project: Path, change: Callable[[Path], None], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """check-stdlib.py on a changed copy. It is stdlib only, so this Python runs it."""
    dst = tmp_path / "p"
    shutil.copytree(project, dst, symlinks=True, ignore=shutil.ignore_patterns(".git", ".venv"))
    change(dst)
    return subprocess.run([sys.executable, "scripts/check-stdlib.py"], cwd=dst, capture_output=True, text=True)


@STDLIB
@pytest.mark.parametrize("case", BREAKS)
def test_check_stdlib_fails(case: str, project: Path, tmp_path: Path) -> None:
    change, message = BREAKS[case]
    result = check_stdlib(project, change, tmp_path)
    assert result.returncode == 1 and message in result.stdout, result.stdout + result.stderr


@STDLIB
@pytest.mark.parametrize("case", ALLOWED)
def test_check_stdlib_allows(case: str, project: Path, tmp_path: Path) -> None:
    result = check_stdlib(project, ALLOWED[case], tmp_path)
    assert (result.returncode, result.stdout) == (0, "stdlib OK\n"), result.stdout + result.stderr


@STDLIB
def test_checks_fail_when_the_literal_version_disagrees(project: Path, tmp_path: Path) -> None:
    """scripts/checks.d/20-python.sh: the program's literal is pyproject.toml's version."""
    dst = tmp_path / "p"
    shutil.copytree(project, dst, symlinks=True, ignore=shutil.ignore_patterns(".git"))
    edit(PROGRAM, '__version__ = "0.0.0"', '__version__ = "0.0.1"')(dst)
    result = checks(commit(dst))
    assert result.returncode != 0
    assert "src/demo/demo.py's __version__ (0.0.1) and pyproject.toml (0.0.0) disagree" in result.stdout, result.stdout
    edit(PROGRAM, '__version__ = "0.0.1"  # x-release-please-version', '__version__ = "0.0.0"')(dst)
    result = checks(commit(dst))
    assert result.returncode != 0 and "no literal with the x-release-please-version marker" in result.stdout
