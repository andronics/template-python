"""Decision 0011: `kind: stdlib-cli`, a command that imports nothing from PyPI and runs as `python3 -IS`.

The render matrix's `stdlib-cli` variant runs its Definition of done (test_python.py, with
scripts/check-stdlib.py); these tests pin what is particular to it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from stacking import checks, commit
from test_python import run

STDLIB = pytest.mark.parametrize("variant", ["stdlib-cli"], indirect=True)
PROGRAM = "src/demo/demo.py"
NOT_RENDERED = ["src/demo/cli.py", "src/demo/config.py", "tests/conftest.py", "tests/unit/test_cli.py",
                "tests/unit/test_config.py", "contrib/demo.example.yaml", "Dockerfile", ".dockerignore",
                "docker", "contrib/systemd", "docs/wiki/Deployment.md", "docs/openapi.json"]  # fmt: skip


@STDLIB
def test_renders_the_program_and_none_of_typer_or_interpose(project: Path) -> None:
    for path in NOT_RENDERED:
        assert not (project / path).exists(), path
    for path in (PROGRAM, "src/demo/__init__.py", "src/demo/__main__.py", "tests/unit/test_demo.py",
                 "scripts/check-stdlib.py"):  # fmt: skip
        assert (project / path).is_file(), path
    assert (project / PROGRAM).read_text().startswith("#!/usr/bin/python3 -IS\n")
    assert '__version__ = "0.0.0"  # x-release-please-version\n' in (project / PROGRAM).read_text()
    # No interpose, Typer or PyYAML anywhere they would be installed, imported or documented.
    looked = [project / p for p in ("pyproject.toml", "uv.lock", ".agents/stack.md", ".github/dependabot.yml")]
    looked += [p for d in ("src", "tests", "scripts", "docs/wiki") for p in (project / d).rglob("*") if p.is_file()]
    for path in looked:
        text = path.read_text().lower()
        for name in ("interpose", "typer", "pyyaml", "import yaml"):
            assert name not in text, f"{path.relative_to(project)} names {name}"


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
    release = (project / "docs/wiki/Release-Process.md").read_text()
    assert "`extra-files`" in release and "**interpose**" not in release
    assert "Bash(uv run demo:*)" in json.loads((project / ".claude/settings.json").read_text())["permissions"]["allow"]


@STDLIB
def test_ci_runs_the_check_and_the_file_alone(project: Path) -> None:
    """stack-ci.yml's test matrix runs check-stdlib.py, and its smoke step runs the program file
    alone with `python -IS`: run that step as CI does."""
    steps = yaml.safe_load((project / ".github/workflows/stack-ci.yml").read_text())["jobs"]["test"]["steps"]
    assert "uv run scripts/check-stdlib.py" in [s.get("run") for s in steps]
    smoke = next(s["run"] for s in steps if s.get("name") == "Import and entry-point smoke test")
    assert 'uv run python -IS "$tmp/demo.py" --version' in smoke
    result = run(project, "bash", "-euo", "pipefail", "-c", smoke)
    assert result.returncode == 0, result.stdout + result.stderr
    broken = smoke.replace('"$want" ]', '"$want-not" ]')
    result = run(project, "bash", "-euo", "pipefail", "-c", broken)
    assert result.returncode != 0 and "--version printed 'demo 0.0.0'" in result.stdout, result.stdout


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
