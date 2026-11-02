from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from stacking import ROOT, commit, copy, sh, sibling, stage  # noqa: E402

# Each render gets a venv: link it to uv's cache instead of copying every package into it.
os.environ.setdefault("UV_LINK_MODE", "symlink")

# The base version this overlay needs, and its tests render (staged copies are tagged with it).
BASE_VERSION = "v2.0.0"
BASE = {"project_name": "demo", "description": "A demo project", "github_owner": "metalayerlab"}

# The render matrix: kind x container_image x contrib (has_cli follows kind). Each one must
# pass its own Definition of done and base's contract cases. `container` adds
# template-container (a sibling checkout) with these answers.
MATRIX: dict[str, dict[str, object]] = {
    "service-image": {"kind": "service", "container_image": True, "contrib": ["docker", "k8s", "systemd"],
                      "puid_pgid": True, "integration_ci": True, "container": {}},
    "service-image-bare": {"kind": "service", "container_image": True, "contrib": [], "container": {"multi_arch": False}},
    "service-systemd": {"kind": "service", "container_image": False, "contrib": ["systemd"]},
    "service": {"kind": "service", "container_image": False, "contrib": []},
    "cli-image": {"kind": "cli", "container_image": True, "image_extras": ["*"], "container": {}},
    "cli": {"kind": "cli", "container_image": False},
    "library": {"kind": "library", "integration_ci": True, "integration_extras": ["*"]},
}  # fmt: skip


@pytest.fixture(scope="session")
def base_src(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """template-base: $TEMPLATE_BASE, or ../template-base."""
    base = sibling("template-base", "TEMPLATE_BASE")
    if base is None:
        pytest.fail("template-base must be checked out next to this repository, or set TEMPLATE_BASE")
    return stage(base, tmp_path_factory.mktemp("src") / "template-base", tag=BASE_VERSION)


@pytest.fixture(scope="session")
def python_src(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return stage(ROOT, tmp_path_factory.mktemp("src") / "template-python")


@pytest.fixture(scope="session")
def container_src(tmp_path_factory: pytest.TempPathFactory) -> Path | None:
    """template-container: $TEMPLATE_CONTAINER, or ../template-container (optional)."""
    found = sibling("template-container", "TEMPLATE_CONTAINER")
    return stage(found, tmp_path_factory.mktemp("src") / "template-container") if found else None


def render(base_src: Path, python_src: Path, dst: Path, container_src: Path | None = None,
           base: dict | None = None, **answers: object) -> Path:  # fmt: skip
    """base, then python, then (with a `container` answer) template-container; bootstrapped."""
    container = answers.pop("container", None)
    copy(base_src, dst, {**BASE, **(base or {})})
    copy(python_src, dst, answers)
    if container is not None:
        if container_src is None:
            pytest.skip("template-container isn't checked out next to this repository (or $TEMPLATE_CONTAINER)")
        copy(container_src, dst, dict(container))  # type: ignore[arg-type]
    sh("sh", "scripts/bootstrap.sh", cwd=dst)
    return commit(dst)


@pytest.fixture(scope="session", params=list(MATRIX))
def variant(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture(scope="session")
def project(variant: str, base_src: Path, python_src: Path, container_src: Path | None,
            tmp_path_factory: pytest.TempPathFactory) -> Path:  # fmt: skip
    return render(base_src, python_src, tmp_path_factory.mktemp(variant) / "demo", container_src, **MATRIX[variant])
