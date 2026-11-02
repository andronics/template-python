"""scripts/tag-check.py (decision 0002): its parsing and tag choice on fixtures, then a run against
a fake GitHub API and a local remote, then the rendered workflow. Nothing here uses the network."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
import yaml
from stacking import GIT, ROOT, sh

SCRIPT = ROOT / "template/scripts/tag-check.py"
_spec = importlib.util.spec_from_file_location("tag_check", SCRIPT)
assert _spec and _spec.loader
tc = importlib.util.module_from_spec(_spec)
sys.modules["tag_check"] = tc  # dataclasses look the module up
_spec.loader.exec_module(tc)

PYPROJECT = """\
[project]
name = "demo"
version = "0.1.0"
dependencies = [
    "interpose @ git+https://github.com/metalayerlab/interpose@v0.1.0",
    # a comment that stays
    "Other_Lib[fast,cli] @ git+https://github.com/acme/other-lib.git@1.4.2 ; python_version >= '3.12'",
    "httpx>=0.27",
]

[project.optional-dependencies]
extra = ["branchy @ git+https://github.com/acme/branchy@main"]

[dependency-groups]
dev = [
    "pinned @ git+https://github.com/acme/pinned@3f2a9c1d4e5b6a7f8091a2b3c4d5e6f708192a3b",
    "early @ git+https://github.com/acme/early@v2.0.0-rc.1",
    "loose @ git+https://github.com/acme/loose",
    {include-group = "lint"},
]
lint = ["ruff>=0.6"]

[tool.uv.sources]
srcdep = { git = "https://github.com/acme/srcdep", tag = "v0.3.1" }
srcbranch = { git = "https://github.com/acme/srcbranch", branch = "dev" }
srcrev = { git = "https://github.com/acme/srcrev", rev = "abc1234" }
local = { path = "../local" }
"""


def pins(text: str = PYPROJECT) -> dict[str, Any]:
    return {p.name: p for p in tc.find_pins(tc.tomllib.loads(text))}


def test_finds_the_inline_form_with_extras_and_markers() -> None:
    found = pins()
    interpose, other = found["interpose"], found["Other_Lib"]
    assert (interpose.slug, interpose.ref, interpose.form, interpose.skip) == (
        "metalayerlab/interpose", "v0.1.0", "direct", "")  # fmt: skip
    assert (other.slug, other.ref, other.key, other.skip) == ("acme/other-lib", "1.4.2", "other-lib", "")
    assert "httpx" not in found and "ruff" not in found and "local" not in found


def test_finds_the_sources_form() -> None:
    src = pins()["srcdep"]
    assert (src.slug, src.ref, src.form, src.skip) == ("acme/srcdep", "v0.3.1", "sources", "")


@pytest.mark.parametrize(("name", "skip"), [
    ("branchy", "branch pin (main)"),
    ("pinned", "commit pin (3f2a9c1d4e5b6a7f8091a2b3c4d5e6f708192a3b)"),
    ("early", "pre-release pin (v2.0.0-rc.1)"),
    ("loose", "not pinned"),
    ("srcbranch", "branch pin (dev)"),
    ("srcrev", "commit pin (abc1234)"),
])  # fmt: skip
def test_skips_branch_commit_and_pre_release_pins(name: str, skip: str) -> None:
    assert pins()[name].skip == skip


@pytest.mark.parametrize(("pin", "tags", "new", "breaking"), [
    ("v0.1.0", ["v0.1.0", "v0.1.1", "v0.1.3", "v0.1.2"], "v0.1.3", ""),
    ("v0.1.0", ["v0.1.1", "v0.2.0", "v0.3.0-rc.1", "nightly", "v0.10"], "v0.2.0", "0.x minor"),
    ("v0.9.4", ["v1.0.0"], "v1.0.0", "major"),
    ("v1.2.0", ["v1.3.0", "v1.2.9"], "v1.3.0", ""),
    ("v1.2.0", ["v1.9.9", "v2.0.0", "v3.1.0"], "v3.1.0", "major"),
    ("1.4.2", ["v1.5.0", "1.5.0", "v1.4.9"], "1.5.0", ""),       # the pin's v style, when both exist
    ("v1.4.2", ["1.5.0"], "1.5.0", ""),                          # else the tag as it is
])  # fmt: skip
def test_picks_the_highest_tag(pin: str, tags: list[str], new: str, breaking: str) -> None:
    bump = tc.choose(tc.Pin("x", "o", "r", pin, "direct"), tags)
    assert (bump.new, bump.breaking) == (new, breaking)
    assert bump.title.endswith(" (breaking)") == bool(breaking)
    assert bump.message == f"chore(deps): bump x from {pin} to {new}"


@pytest.mark.parametrize("tags", [[], ["v0.1.0"], ["v0.0.9", "v0.1.0", "v0.2.0-rc.1", "main"]])
def test_no_bump_when_current(tags: list[str]) -> None:
    assert tc.choose(tc.Pin("x", "o", "r", "v0.1.0", "direct"), tags) is None


@pytest.mark.parametrize(("name", "new", "line"), [
    ("interpose", "v0.2.0", '    "interpose @ git+https://github.com/metalayerlab/interpose@v0.2.0",'),
    ("Other_Lib", "1.5.0", ("    \"Other_Lib[fast,cli] @ git+https://github.com/acme/other-lib.git@1.5.0"
                            " ; python_version >= '3.12'\",")),
    ("srcdep", "v0.4.0", 'srcdep = { git = "https://github.com/acme/srcdep", tag = "v0.4.0" }'),
])  # fmt: skip
def test_rewrites_only_the_pins_line(name: str, new: str, line: str) -> None:
    text = PYPROJECT + '# interpose @ git+https://github.com/metalayerlab/interpose@v0.1.0 in a comment\n'
    bump = tc.Bump(pins()[name], new)
    bump.lines = tc.pin_lines(text, bump.pin)
    assert len(bump.lines) == 1
    after = tc.rewrite(text, bump)
    changed = [(a, b) for a, b in zip(text.splitlines(), after.splitlines(), strict=True) if a != b]
    assert [b for _, b in changed] == [line]


def test_no_pins_is_a_no_op(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\ndependencies = ["httpx"]\n')
    assert tc.main(["--root", str(tmp_path)]) == 0  # not even --dry-run: it needs no token or repo
    assert capsys.readouterr().out == "tag-check: no tag-pinned git dependencies\n"


def test_dry_run_with_tags_from_a_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    tags = {"metalayerlab/interpose": ["v0.1.0", "v0.2.0"], "acme/other-lib": ["1.4.2"],
            "acme/srcdep": ["v0.3.2"]}  # fmt: skip
    (tmp_path / "tags.json").write_text(json.dumps(tags))
    assert tc.main(["--root", str(tmp_path), "--dry-run", "--tags-from", str(tmp_path / "tags.json")]) == 0
    out = capsys.readouterr().out
    assert "chore(deps): bump interpose from v0.1.0 to v0.2.0 (breaking)\n  pyproject.toml:5:" in out
    assert "chore(deps): bump srcdep from v0.3.1 to v0.3.2\n" in out
    assert "| [Other_Lib](https://github.com/acme/other-lib) | `1.4.2` | current |" in out
    assert "skipped: branch pin (main)" in out and "skipped: pre-release pin (v2.0.0-rc.1)" in out
    assert tc.SQUAT in out
    assert (tmp_path / "pyproject.toml").read_text() == PYPROJECT


# A fake GitHub: the tags of each repository, the open PRs, and every request made.
class FakeGitHub:
    def __init__(self) -> None:
        self.tags: dict[str, list[str]] = {}
        self.open: dict[str, int] = {}  # head branch -> PR number
        self.requests: list[tuple[str, str, Any]] = []


@pytest.fixture
def github() -> Iterator[tuple[FakeGitHub, str]]:
    fake = FakeGitHub()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

        def reply(self, status: int, data: object) -> None:
            raw = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def handle_any(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length)) if length else None
            fake.requests.append((self.command, self.path, body))
            assert self.headers["Authorization"] == "Bearer t0ken"
            path, _, query = self.path.partition("?")
            params = dict(p.split("=", 1) for p in query.split("&") if p)
            parts = path.strip("/").split("/")
            if parts[-1] == "tags":
                slug = "/".join(parts[1:3])
                if slug not in fake.tags:
                    return self.reply(404, {"message": "Not Found"})
                page = int(params.get("page", 1))
                names = fake.tags[slug][(page - 1) * 100 : page * 100]
                return self.reply(200, [{"name": n} for n in names])
            if parts[-1] == "pulls" and self.command == "GET":
                head = params["head"].split(":", 1)[1]
                return self.reply(200, [{"number": fake.open[head]}] if head in fake.open else [])
            if parts[-1] == "pulls" and self.command == "POST":
                fake.open[body["head"]] = 7
                return self.reply(201, {"number": 7})
            return self.reply(200, {})

        do_GET = do_POST = do_PATCH = handle_any

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield fake, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A project on main, its bare origin, and a bin/ whose `uv` records its arguments in uv.lock."""
    origin, work, bin_ = tmp_path / "origin.git", tmp_path / "work", tmp_path / "bin"
    sh("git", "init", "-q", "--bare", "-b", "main", str(origin), cwd=tmp_path)
    work.mkdir()
    (work / "pyproject.toml").write_text(PYPROJECT)
    (work / "uv.lock").write_text("version = 1\n")
    sh("git", "init", "-q", "-b", "main", cwd=work)
    sh("git", "remote", "add", "origin", str(origin), cwd=work)
    sh("git", "add", "-A", cwd=work)
    sh(*GIT, "commit", "-qm", "init", cwd=work)
    sh("git", "push", "-q", "origin", "main", cwd=work)
    bin_.mkdir()
    (bin_ / "uv").write_text('#!/bin/sh\necho "uv $*" >> uv.lock\n')
    (bin_ / "uv").chmod(0o755)
    return work, origin, bin_


def run(work: Path, bin_: Path, api: str, **env: str) -> subprocess.CompletedProcess[str]:
    environ = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}", "GITHUB_API_URL": api,
               "GITHUB_REPOSITORY": "me/demo", "GH_TOKEN": "t0ken",
               "GIT_AUTHOR_NAME": "bot", "GIT_AUTHOR_EMAIL": "bot@example.org",
               "GIT_COMMITTER_NAME": "bot", "GIT_COMMITTER_EMAIL": "bot@example.org", **env}  # fmt: skip
    return subprocess.run([sys.executable, str(SCRIPT)], cwd=work, capture_output=True, text=True, env=environ)


def test_opens_one_pr_per_dependency(github: tuple[FakeGitHub, str], repo: tuple[Path, Path, Path]) -> None:
    fake, api = github
    work, origin, bin_ = repo
    # interpose's newest tag is on the second page of 100.
    fake.tags = {"metalayerlab/interpose": [f"v0.0.{i}" for i in range(100)] + ["v0.2.0", "v0.1.1"],
                 "acme/other-lib": ["1.4.2"], "acme/srcdep": ["v0.3.1"]}  # fmt: skip
    result = run(work, bin_, api)
    assert result.returncode == 0, result.stdout + result.stderr

    branches = sh("git", "for-each-ref", "--format=%(refname:short)", "refs/heads", cwd=origin).split()
    assert branches == ["main", "tag-check/interpose"]
    log = sh("git", "log", "--format=%s", "main..tag-check/interpose", cwd=origin).splitlines()
    assert log == ["chore(deps): bump interpose from v0.1.0 to v0.2.0"]
    files = sh("git", "diff", "--name-only", "main", "tag-check/interpose", cwd=origin).split()
    assert files == ["pyproject.toml", "uv.lock"]
    diff = sh("git", "diff", "-U0", "main", "tag-check/interpose", "--", "pyproject.toml", cwd=origin)
    assert [ln for ln in diff.splitlines() if ln[:1] in "+-" and ln[:3] not in ("+++", "---")] == [
        '-    "interpose @ git+https://github.com/metalayerlab/interpose@v0.1.0",',
        '+    "interpose @ git+https://github.com/metalayerlab/interpose@v0.2.0",',
    ]
    lock = sh("git", "show", "tag-check/interpose:uv.lock", cwd=origin)
    assert lock == "version = 1\nuv lock --upgrade-package interpose\n"

    (created,) = [b for m, p, b in fake.requests if m == "POST" and p == "/repos/me/demo/pulls"]
    assert created["title"] == "chore(deps): bump interpose from v0.1.0 to v0.2.0 (breaking)"
    assert (created["head"], created["base"]) == ("tag-check/interpose", "main")
    assert "https://github.com/metalayerlab/interpose/compare/v0.1.0...v0.2.0" in created["body"]
    assert "**Breaking:** a 0.x minor bump" in created["body"]
    assert "close and reopen this PR" in created["body"]  # GITHUB_TOKEN: CI didn't run
    assert "opened #7" in result.stdout and "skipped: branch pin (main)" in result.stdout
    assert sh("git", "branch", "--show-current", cwd=work).strip() == "main"
    assert (work / "pyproject.toml").read_text() == PYPROJECT

    # A newer tag rewrites the same branch and edits the open PR; with the App, no CI note.
    fake.tags["metalayerlab/interpose"].append("v0.2.1")
    fake.requests.clear()
    result = run(work, bin_, api, RELEASE_APP_CLIENT_ID="12345")
    assert result.returncode == 0, result.stdout + result.stderr
    log = sh("git", "log", "--format=%s", "main..tag-check/interpose", cwd=origin).splitlines()
    assert log == ["chore(deps): bump interpose from v0.1.0 to v0.2.1"]
    (edited,) = [b for m, p, b in fake.requests if m == "PATCH"]
    assert edited["title"].endswith("to v0.2.1 (breaking)") and "close and reopen" not in edited["body"]
    assert not [r for r in fake.requests if r[0] == "POST"]


def test_closes_the_pr_once_current(github: tuple[FakeGitHub, str], repo: tuple[Path, Path, Path]) -> None:
    fake, api = github
    work, _, bin_ = repo
    fake.tags = {"metalayerlab/interpose": ["v0.1.0"], "acme/other-lib": [], "acme/srcdep": []}
    fake.open["tag-check/interpose"] = 3
    result = run(work, bin_, api)
    assert result.returncode == 0, result.stdout + result.stderr
    writes = [(m, p, b) for m, p, b in fake.requests if m != "GET"]
    assert writes[0][:2] == ("POST", "/repos/me/demo/issues/3/comments")
    assert writes[1] == ("PATCH", "/repos/me/demo/pulls/3", {"state": "closed"})
    assert "current; closed #3" in result.stdout
    assert sh("git", "branch", "-r", cwd=work).split() == ["origin/main"]


def test_an_unreadable_dependency_fails_the_job(github: tuple[FakeGitHub, str],
                                                repo: tuple[Path, Path, Path]) -> None:  # fmt: skip
    fake, api = github
    work, _, bin_ = repo
    fake.tags = {"acme/other-lib": ["1.4.2"], "acme/srcdep": ["v0.3.1"]}  # interpose: 404
    result = run(work, bin_, api)
    assert result.returncode == 1
    assert "error: interpose: can't read metalayerlab/interpose's tags" in result.stderr
    assert "release App" in result.stderr


def test_workflow(project: Path) -> None:
    """Rendered in every project; actionlint checks it with the rest (test_docker_checks)."""
    path = project / ".github/workflows/python-tag-check.yml"
    text = path.read_text()
    assert text.startswith("# Template-owned: template-python.")
    flow = yaml.safe_load(text)
    assert flow[True] == {"schedule": [{"cron": "0 5 * * 1"}], "workflow_dispatch": None}
    assert flow["permissions"] == {"contents": "write", "pull-requests": "write"}
    assert flow["concurrency"]["group"] == "tag-check"
    steps = flow["jobs"]["tag-check"]["steps"]
    assert steps[0]["if"] == "vars.RELEASE_APP_CLIENT_ID != ''"
    assert all("@" in s["uses"] and len(s["uses"].split("@")[1]) == 40 for s in steps if "uses" in s)
    assert "python3 scripts/tag-check.py" in steps[-1]["run"]


def test_rendered_script_is_a_no_op(project: Path) -> None:
    """A new project has no tag-pinned dependency: the run says so and exits 0."""
    result = subprocess.run([sys.executable, "scripts/tag-check.py"], cwd=project, capture_output=True, text=True)
    assert (result.returncode, result.stdout) == (0, "tag-check: no tag-pinned git dependencies\n"), result.stderr
