#!/usr/bin/env bash
# Template-owned: template-python. Lint the Markdown: what stack-ci.yml's Markdown lint job
# runs, with the same version and arguments (it calls this script). Uses markdownlint-cli2
# 0.24.0 when it is installed (on PATH or in the runner's tools folder), else the pinned Docker
# image. With neither it skips locally, but is an error in CI. A self-hosted runner without Docker
# installs it once into its tools folder (a pinned version, never fetched at job time):
#   npm install --prefix "$CI_TOOLS_BIN/../markdownlint" markdownlint-cli2@0.24.0
#   ln -s ../markdownlint/node_modules/.bin/markdownlint-cli2 "$CI_TOOLS_BIN/markdownlint-cli2" Quiet on a pass: one summary line; the tool's output in
# full on a failure. Config: .markdownlint-cli2.yaml (CHANGELOG.md is release-please's).
set -euo pipefail
cd "$(dirname "$0")/.."

# The tool itself, pinned by version: on PATH first, then in the runner's tools folder
# ($CI_TOOLS_BIN, default the desktop runner's), and used only when it reports exactly the
# pinned version; otherwise the pinned Docker image below (A42: binary first, Docker as fallback).
find_tool() {
    local name="$1" want="$2" flag="$3" cand
    for cand in "$(command -v "$name" 2> /dev/null || true)" \
        "${CI_TOOLS_BIN-${HOME:-/nonexistent}/.local/share/actions-runner/tools/bin}/$name"; do
        [ -n "$cand" ] && [ -x "$cand" ] || continue
        if "$cand" "$flag" 2> /dev/null | head -n 1 | grep -Eq "(^|[ v])${want//./\\.}( |$)"; then
            echo "$cand"
            return 0
        fi
    done
    return 1
}

MDL_VERSION=0.24.0
mdl_cmd=()
if bin="$(find_tool markdownlint-cli2 "v$MDL_VERSION" --version)"; then
    mdl_cmd=("$bin")
elif command -v docker > /dev/null 2>&1; then
    mdl_cmd=(docker run --rm -v "$PWD:/workdir" "davidanson/markdownlint-cli2:v$MDL_VERSION")
else
    if [ "${CI:-}" = "true" ]; then
        echo "error: neither markdownlint-cli2 $MDL_VERSION nor docker is installed"
        exit 1
    fi
    echo "skip: neither markdownlint-cli2 $MDL_VERSION nor docker is installed"
    exit 0
fi

if out="$("${mdl_cmd[@]}" \
        "docs/wiki/*.md" "*.md" "!CHANGELOG.md" 2>&1)"; then
    echo "check-markdown OK"
else
    printf 'error: markdownlint\n%s\n' "$out"
    exit 1
fi
