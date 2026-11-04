"""The wiki's settings table (scripts/gen-wiki.py): each kind of setting's row, section settings
(interpose v0.4.0's `is_section`) included, in every variant that has the table.

The rows come from stand-ins for interpose's `Setting`, so the template's interpose pin needn't move
to cover a newer interpose: gen-wiki.py reads only the settings' attributes.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import MATRIX


@dataclass(frozen=True)
class Setting:
    """interpose v0.4.0's Setting, as far as gen-wiki.py reads it."""

    key: str
    default: str | int | bool
    help: str
    secret: bool = False
    is_list: bool = False
    is_section: bool = False
    prefix: str = "DEMO_"

    @property
    def env(self) -> str:
        return self.prefix + self.key.upper().replace(".", "_")


# A setting of each kind before sections, and the row it has always had.
UNCHANGED = [
    (Setting("listen.port", 8080, "Port to listen on."), "| `listen.port` | `DEMO_LISTEN_PORT` | `8080` | Port to listen on. |"),
    (Setting("debug", False, "Log more."), "| `debug` | `DEMO_DEBUG` | `False` | Log more. |"),
    (Setting("name", "", "A | name."), "| `name` | `DEMO_NAME` | *(none)* | A \\| name. |"),
    (Setting("hosts", "", "Hosts.", is_list=True),
     "| `hosts` | `DEMO_HOSTS` | *(empty list)* | Hosts. A list: YAML, or comma-separated. |"),
    (Setting("api.token", "", "Token.", secret=True),
     "| `api.token` | `DEMO_API_TOKEN` | *(none)* | Token. 🔒 Secret: use the `_FILE` variant. |"),
    # A config.py from before list settings, or on interpose before v0.4.0: no is_list, no is_section.
    (SimpleNamespace(key="old", env="DEMO_OLD", default="x", help="Old.", secret=False),
     "| `old` | `DEMO_OLD` | `x` | Old. |"),
]  # fmt: skip
SECTIONS = [
    (Setting("upstream", "", "The upstream server.", is_section=True),
     ("| `upstream` | `DEMO_UPSTREAM_FILE` | *(empty)* | The upstream server. "
     "A section: YAML, from the config file or the `_FILE` variable's file. |")),
    (Setting("routes", "", "The routes.", is_list=True, is_section=True),
     ("| `routes` | `DEMO_ROUTES_FILE` | *(empty list)* | The routes. "
     "A list of sections: YAML, from the config file or the `_FILE` variable's file. |")),
]  # fmt: skip
HEADER = ["| Key | Environment variable | Default | Description |", "|---|---|---|---|"]


def _table(project: Path, monkeypatch: pytest.MonkeyPatch, settings: list[object]) -> str:
    """The project's own gen-wiki.py settings(), run on `settings` as demo.config.SETTINGS."""
    spec = importlib.util.spec_from_file_location(f"gen_wiki_{id(project)}", project / "scripts/gen-wiki.py")
    assert spec is not None and spec.loader is not None
    gen_wiki = importlib.util.module_from_spec(spec)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)  # the project is shared by the variant's tests
    spec.loader.exec_module(gen_wiki)
    config = types.ModuleType("demo.config")
    config.SETTINGS = settings  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "demo", types.ModuleType("demo"))
    monkeypatch.setitem(sys.modules, "demo.config", config)
    if "settings" not in gen_wiki.BLOCKS:
        return ""
    return str(gen_wiki.BLOCKS["settings"]())


def test_rows_before_sections_are_unchanged(project: Path, variant: str, monkeypatch: pytest.MonkeyPatch) -> None:
    table = _table(project, monkeypatch, [s for s, _ in UNCHANGED])
    if MATRIX[variant]["kind"] in ("library", "stdlib-cli"):
        assert table == "", "no settings block without config.py"
        return
    assert table == "\n".join([*HEADER, *(row for _, row in UNCHANGED)])


def test_section_rows(project: Path, variant: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A section's row names its `_FILE` variable only, as "section" or "list of sections", with an empty
    default; the rows around it don't change."""
    if MATRIX[variant]["kind"] in ("library", "stdlib-cli"):
        pytest.skip("no settings block without config.py")
    settings = [UNCHANGED[0][0], *(s for s, _ in SECTIONS), UNCHANGED[3][0]]
    rows = [UNCHANGED[0][1], *(row for _, row in SECTIONS), UNCHANGED[3][1]]
    assert _table(project, monkeypatch, settings) == "\n".join([*HEADER, *rows])
