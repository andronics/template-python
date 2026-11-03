"""Decision 0003: service and cli projects get a thin config.py on interpose; libraries get nothing."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import MATRIX
from test_python import DOD, run

# Byte-identical to 0003 and, but for the tag, to the first consumers (metalayerlab/mitm-proxy#10,
# sluice#52), so their next template update is at most a one-line pin conflict.
PIN = '    "interpose @ git+https://github.com/metalayerlab/interpose@v0.2.0",\n'
METADATA = (
    "[tool.hatch.metadata]\n"
    "# interpose is pinned by its git URL, not PyPI (template-python decision 0003)\n"
    "allow-direct-references = true\n"
)


def test_interpose_only_with_a_cli(project: Path, variant: str) -> None:
    pyproject = (project / "pyproject.toml").read_text()
    dependabot = (project / ".github/dependabot.yml").read_text()
    if MATRIX[variant]["kind"] == "library":
        assert "interpose" not in pyproject + dependabot
        assert not (project / "src/demo/config.py").exists()
        return
    assert pyproject.split("dependencies = [\n", 1)[1].startswith(PIN), "the pin is the first dependency"
    wheel = '[tool.hatch.build.targets.wheel]\npackages = ["src/demo"]\n'
    assert wheel + "\n" + METADATA + "\n[tool.ruff]\n" in pyproject
    assert "ignore:\n      - dependency-name: interpose\n" in dependabot
    if (project / "Dockerfile").is_file():
        builder = (project / "Dockerfile").read_text().split("# Stage 2: runtime")[0]
        assert "set -- git $(sed -n 's/^build://p' /tmp/system-packages.txt)" in builder
    # The engine is interpose's: none of it is left in the project.
    config = (project / "src/demo/config.py").read_text()
    assert "from interpose.settings import" in config
    assert not any(f"def {name}(" in config for name in ("_coerce", "resolve", "read_file", "_lookup"))
    # interpose v0.2.0's typed accessors narrow each value; nothing is cast or re-cased (0003).
    assert "cast(" not in config and ".upper()" not in config


# A project adds a secret and a level-style setting, read with the accessors as 0003 says.
SECRET_IMPORT = "from interpose.secret import Secret\n"
SETTINGS_ADDED = """\
        Setting("api.token", "", "Token for the upstream API.", secret=True),
        Setting(
            "upstream.log_level",
            "WARNING",
            "The upstream client's log level.",
            check=one_of(*LOG_LEVELS),
        ),
"""
FIELDS_ADDED = "    api_token: Secret\n    upstream_log_level: str\n"
VALUES_ADDED = """\
        api_token=resolved.secret("api.token"),
        upstream_log_level=resolved.str("upstream.log_level"),
"""
TEST = '''\
from collections.abc import Callable
from pathlib import Path

import pytest
from interpose.secret import Secret
from typer.testing import CliRunner

from demo.cli import app
from demo.config import SETTINGS, ConfigError, load_config


def test_secret_from_its_file(tmp_path: Path) -> None:
    token = tmp_path / "token"
    token.write_text("s3cret\\n", encoding="utf-8")
    cfg = load_config(tmp_path / "missing.yaml", environ={"DEMO_API_TOKEN_FILE": str(token)})
    assert isinstance(cfg.api_token, Secret)
    assert cfg.api_token.reveal() == "s3cret"
    assert str(cfg.api_token) == f"{cfg.api_token}" == "********"
    assert "s3cret" not in repr(cfg)
    assert cfg.sources["api.token"] == "DEMO_API_TOKEN_FILE"


def test_unset_secret_is_false(tmp_path: Path) -> None:
    assert not load_config(tmp_path / "missing.yaml", environ={}).api_token


def test_secret_is_masked_by_the_config_command(tmp_path: Path) -> None:
    token = tmp_path / "token"
    token.write_text("s3cret\\n", encoding="utf-8")
    result = CliRunner().invoke(
        app, ["config", "-c", str(tmp_path / "missing.yaml")], env={"DEMO_API_TOKEN_FILE": str(token)}
    )
    assert result.exit_code == 0, result.output
    assert "api.token = ******** (set)  (DEMO_API_TOKEN_FILE)" in result.stdout
    assert "s3cret" not in result.output


def test_str_of_a_secret_is_refused(tmp_path: Path) -> None:
    resolved = SETTINGS.resolve(tmp_path / "missing.yaml", {})
    with pytest.raises(TypeError, match=r"'api\\.token' is a secret setting, not str: use secret"):
        resolved.str("api.token")


def test_level_setting_is_the_declared_spelling(write_config: Callable[..., Path]) -> None:
    cfg = load_config(write_config("upstream:\\n  log_level: debug\\n"), environ={})
    assert (cfg.upstream_log_level, cfg.sources["upstream.log_level"]) == ("DEBUG", "file")
    cfg = load_config(write_config(""), environ={"DEMO_UPSTREAM_LOG_LEVEL": "Error"})
    assert cfg.upstream_log_level == "ERROR"


def test_level_setting_is_checked(write_config: Callable[..., Path]) -> None:
    with pytest.raises(ConfigError, match=r"upstream\\.log_level: expected one of DEBUG"):
        load_config(write_config("upstream:\\n  log_level: loud\\n"), environ={})
'''


def _insert(text: str, before: str, added: str) -> str:
    assert text.count(before) == 1, before
    return text.replace(before, added + before)


@pytest.mark.parametrize("variant", ["cli", "service"], indirect=True)
def test_a_secret_and_a_level_setting(project: Path, tmp_path: Path) -> None:
    """The pattern 0003 tells projects to copy: secret() and str(), a Secret revealed at use.
    ruff, strict mypy and the tests pass on it, and the wiki's table and `config` mask the secret."""
    copy = tmp_path / "demo"
    shutil.copytree(project, copy, symlinks=True, ignore=shutil.ignore_patterns(".venv"))
    path = copy / "src/demo/config.py"
    config = path.read_text()
    config = _insert(config, "from interpose.settings import", SECRET_IMPORT)
    config = _insert(config, "    ),\n    default_path=", SETTINGS_ADDED)
    config = _insert(config, "    # Setting key -> where", FIELDS_ADDED)
    config = _insert(config, "        sources=dict(", VALUES_ADDED)
    path.write_text(config)
    # test_keys_and_variables pins the list on purpose: adding a setting changes it.
    tests = copy / "tests/unit/test_config.py"
    keys = '        ("api.token", "DEMO_API_TOKEN"),\n        ("upstream.log_level", "DEMO_UPSTREAM_LOG_LEVEL"),\n'
    tests.write_text(_insert(tests.read_text(), "    ]\n    assert CONFIG_ENV", keys))
    (copy / "tests/unit/test_secret_and_level.py").write_text(TEST)
    # Formatting the additions is the project's job; what they must pass is lint, types and tests.
    run(copy, "uv", "run", "ruff", "format", "src", "tests")
    regenerate = run(copy, "uv", "run", "scripts/gen-wiki.py")
    assert regenerate.returncode == 0, regenerate.stdout + regenerate.stderr
    page = (copy / "docs/wiki/In-Depth-Configuration.md").read_text()
    assert "| `api.token` | `DEMO_API_TOKEN` | *(none)* | Token for the upstream API. 🔒 Secret" in page
    for cmd in DOD:
        result = run(copy, *cmd)
        assert result.returncode == 0, f"{' '.join(cmd)}:\n{result.stdout}\n{result.stderr}"
    result = subprocess.run(["git", "diff", "--stat"], cwd=copy, capture_output=True, text=True)
    assert "uv.lock" not in result.stdout, "the lock file is unchanged"
