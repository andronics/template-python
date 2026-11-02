# 0003: A thin `config.py` on interpose

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Proposed
Date: 2026-11-02
Authors: Stephen Cox; drafted by Claude (Claude Code)

## Context

Every `service` and `cli` project gets its own copy of the settings engine in `src/<pkg>/config.py`
(`Setting`, `_coerce`, `resolve`, `read_file`, `ConfigError`). `src/**` is in `_skip_if_exists`, so the
copy is the project's from the first render and a template fix never reaches it. The copies drifted
(project-template#84): a YAML `0.5` silently `0`, a list's repr for a str setting, `is_list` in one
project only. project-template's design
[0020](https://github.com/metalayerlab/project-template/blob/v0.1.23/docs/design/0020-thin-config-on-interpose.md)
(Proposed, 2026-11-01) answered this with a thin `config.py` on a shared library. That role now belongs
here: [0001](0001-python-overlay.md) left 0020 open. This record replaces it; where they differ, this wins.

[metalayerlab/interpose](https://github.com/metalayerlab/interpose) **v0.1.0** (tagged 2026-11-02) is that
library. Its public API, on `main`:

- `interpose.settings`: `Setting(key, default, help, secret=False, is_list=False, check=None)`;
  `Settings(prefix, settings, *, default_path)`, a `Sequence[Setting]` that binds the prefix (so
  `setting.env` works) and has `config_env`; `Settings.resolve(path=None, environ=None) -> Resolved(values,
  sources)`; `ConfigError`; `Value`; the checks `port`, `positive`, `non_negative`, `one_of`.
- `interpose.secret`: `Secret` (`str()`, `repr()` and `format()` give `MASK`, `"********"`; `reveal()`
  gives the value; `bool()` says whether it's set), `read_secret_dir`.

Its PR #2 lists 13 places where the design met its consumers. The ones a generated project notices:

| PR #2 | Today's skeleton | On interpose |
|---|---|---|
| 3 `str()` of a Secret | n/a (no `Secret`) | `"********"`, not the value |
| 7 `_FILE` | both ends stripped | trailing whitespace only |
| 5 int from the environment | `int()`, so `1_000` | ASCII digits and a sign |
| 8 errors | `cannot read <path>: <pyyaml's message>` | `cannot parse <path> at line L, column C: ...`; coercion errors end `(from <source>)` |
| 9 `check` | n/a | runs on the default too |
| 1, 12 declaration | anything goes | `ValueError` at import: a secret int/bool/list, two settings sharing a variable, a key part YAML doesn't read as a string (`on`, `no`) |

The rest (4, 6, 10, 11, 13) change nothing a generated project sees. The lookup order, the env var names,
the `config` command's output and the generated settings table don't change.

## Decision

### `config.py` stays project-owned, and becomes thin

`src/[[ package_name ]]/config.py` is still seeded once (`src/**`), but holds only what is the project's:

```python
from interpose.settings import ConfigError, Setting, Settings, one_of, port

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

SETTINGS = Settings(
    "[[ env_prefix ]]",
    (
        Setting("log_level", "INFO", "Log level: ...", check=one_of(*LOG_LEVELS)),
        Setting("listen.port", [[ port ]], "Port the HTTP server listens on.", check=port),  # service
        ...
    ),
    default_path=Path("/etc/[[ project_name ]]/config.yaml"),
)
CONFIG_ENV = SETTINGS.config_env
__all__ = ["CONFIG_ENV", "SETTINGS", "Config", "ConfigError", "load_config"]


def load_config(path: Path | None = None, environ: Mapping[str, str] | None = None) -> Config:
    v = SETTINGS.resolve(path, environ)
    # Cross-setting rules here; single-value rules are check= above.
    return Config(log_level=cast(str, v.values["log_level"]).upper(), ..., sources=dict(v.sources))
```

A project owns its `SETTINGS` entries, its `Config` dataclass and `load_config`'s cross-setting rules
(sluice's `secrets.dir`, mitm-proxy's `ca.cert` with `ca.key`). interpose owns the engine. Once the engine
is out there is nothing left in the file for the template to fix, so the drift ends without moving the file
out of `src/**`.

**The contract** between it and the template-owned files, stated in its docstring: `config.py` exports
`SETTINGS` (iterable; each item has `key`, `env`, `default`, `help`, `secret`, optionally `is_list`),
`CONFIG_ENV`, `Config` (with `sources`), `ConfigError` and `load_config(path=None, environ=None)`.
`cli.py`, its tests and `scripts/gen-wiki.py` use only these, so an unmigrated project's `config.py`
satisfies them too.

`test_config.py` keeps the project's behaviour (each source end to end, defaults, the log level and port
rules, a non-mapping file, invalid YAML matching `cannot parse`) and drops the coercion tests, which are
interpose's.

### The dependency: every `service` and `cli`, no Copier question

`pyproject.toml.jinja` adds, for `has_cli`, as the **first** entry of `dependencies` (before `pyyaml`,
alphabetical), and a block after `[tool.hatch.build.targets.wheel]`:

```toml
    "interpose @ git+https://github.com/metalayerlab/interpose@v0.1.0",
```

```toml
[tool.hatch.metadata]
# interpose is pinned by its git URL, not PyPI (template-python decision 0003)
allow-direct-references = true
```

Without the second, hatchling refuses to build (`cannot be a direct reference unless ...
allow-direct-references`), which the image's `uv sync --no-editable` does (checked with uv 0.13.6).
`pyyaml` and `types-pyyaml` stay: project code may import `yaml`, and removing a line from a merged file
churns every project. A library gets neither: it has no `config.py`.

The pin is the PEP 508 form, not `[tool.uv.sources]`: the URL is then in the built wheel's metadata, so
no installer can take a PyPI `interpose` instead ([0002](0002-tag-check-workflow.md), Context).

### What else the template changes

- **Dockerfile builder:** installs `git` for `has_cli`. uv 0.13.6 locks a GitHub dependency without git,
  but `uv sync --frozen` fails with "Git executable not found" in `python:3.13-slim` (checked). Builder
  stage only; the runtime image is unchanged.
- **`dependabot.yml`:** the `uv` entry ignores `interpose` for `has_cli` (0002, squatting).
- **`scripts/gen-wiki.py`:** unchanged code. It reads only the contract's attributes, and keeps
  `getattr(s, "is_list", False)`: sluice's `config.py` (from project-template v0.1.15) has no `is_list`
  until its switch merges, and a project may keep its own engine indefinitely.
- **`cli.py`:** unchanged. `config` keeps printing `********` for `setting.secret`, which is right for
  both shapes.
- **Updates to interpose** arrive as tag-check PRs (0002). The template's pin moves only when the skeleton
  needs a newer interpose, never on every interpose release: each move is a one-line merge in every
  project, and a conflict where tag-check already moved it further.

### What `str(Secret) == "********"` means for generated code

- The skeleton has no secret setting, so a new project renders no `Secret` and nothing changes.
- A project that adds `secret=True` gets a `Secret` in `Resolved.values`. `Config` holds it as `Secret`
  and the code calls `.reveal()` at the point of use (a header, a connection string). `str()` or an
  f-string gives `********`, silently: a wrong credential is sent, not leaked, but nothing fails at load.
  So `load_config` narrows with `cast(Secret, ...)`, never `str(...)`, and the skeleton does the same for
  its non-secret values (`cast(str, ...)`), so the pattern copied is the safe one.
- `.agents/stack.md`'s Config line gains one sentence: "A secret is a `Secret`: `.reveal()` where it's
  used; `str()` gives `********`." About 70 characters.

### Migration, and the interpose switches already under way

`config.py` and `tests/**` are project-owned, so a template update can't rewrite them. It brings the
`pyproject.toml` lines, the Dockerfile's git, the `dependabot.yml` ignore and 0002's workflow. The project
then does what 0020 described, in a PR of its own (a short design record, as a new dependency needs):
replace its engine with `Settings(...)`, move single-value checks to `check=`, delete its engine tests, and
show that `config`'s output and the settings table are unchanged. A project that skips it keeps working on
its own copy, with an unused dependency, and loses only future engine fixes. A prompt for it goes in
`docs/migrating/interpose-config.md`.

**sluice and mitm-proxy are being switched by another session (andronics-3e)**, by hand, before this
lands. So that the template change doesn't collide with theirs:

1. This record changes nothing in either repository; their switch PRs stay theirs.
2. **Their `pyproject.toml` lines must be byte-identical to the two above, at the same place** (first
   dependency; the `[tool.hatch.metadata]` block after `[tool.hatch.build.targets.wheel]`). Their next
   template update then sees the same change on both sides of the 3-way merge, and it is clean. A newer tag
   on their side is a one-line conflict: keep theirs.
3. **Their images need git in the builder now**, before the template has it. They add `git` to the
   `build:` line of `contrib/system-packages.txt` (project-owned), not to the template-owned
   `Dockerfile`. When the template's Dockerfile installs git itself, the duplicate is harmless and the line
   can go.
4. They need 0002's workflow to hear about `v0.1.1`. Until it ships, a bump is by hand.
5. mitm-proxy's `load_config` reads `str(values["proxy.auth"])` today. On interpose that is `********`,
   which fails its own `user:password` check: loud, not a leak, but the switch must `cast(Secret, ...)`
   and `.reveal()` (PR #2, item 3).
6. Implementation here lands after their stacked-template PRs (sluice #49, mitm-proxy #8), which pin
   template-python v2.0.0, so neither has to rebase on it.

## Alternatives considered

- **A template-owned `config.py`** (taken out of `src/**`), importing a project-owned `settings.py` for
  `SETTINGS` and the rules. Template fixes would reach it, but with the engine in interpose there is
  nothing to fix: what's left is glue. It splits one concept over two files and renames the module every
  project's `cli.py` and tests import. *Rejected.*
- **A template-owned engine file, no library** (`src/<pkg>/_settings.py`). Weighed in interpose's 0001 and
  0020: it ties engine fixes to template releases and puts `Secret` in projects that don't need it.
  *Rejected.*
- **A Copier question, `settings_engine: interpose|none`.** `none` keeps today's in-tree engine, the very
  copy that drifts, in the render matrix and its tests forever. A project that won't depend on GitHub
  keeps its own `config.py` (it's project-owned) and deletes the dependency line, which later updates
  preserve. *Rejected.*
- **`[tool.uv.sources]` with a bare `interpose` requirement**, so Dependabot #16151 could update it. The
  built metadata would then send a non-uv installer to PyPI. *Rejected* (0002).
- **A release archive URL** (`.../archive/refs/tags/v0.1.0.tar.gz`): no git in the image, but uv.lock
  pins its sha256 and GitHub doesn't promise stable archive bytes; a regenerated archive breaks every
  frozen build. *Rejected.*
- **Dropping `pyyaml` from the dependencies**, since interpose brings it. Every project's merged
  `pyproject.toml` would lose a line its own code may need. *Rejected.*
- **Typed accessors instead of `cast`** (`Resolved.str("key")`, `.secret("key")`). Better, but interpose's
  API, not this template's: open question 3.

## Consequences

- **Copier questions:** none.
- **What projects get:** new `service` and `cli` projects start on interpose, with a shorter `config.py`
  and `test_config.py`. Existing ones get the dependency, git in the builder and the Dependabot ignore,
  and migrate `config.py` when they choose. Libraries: nothing.
- **Behaviour** after a project migrates is the table in Context: the same keys, variables and output, a
  stricter engine and different error texts. Tests that match old messages change.
- **Network:** locking and building need GitHub, as they already need PyPI. A builder stage gets bigger by
  git's packages.
- **`.agents/stack.md` budget:** about 70 characters more. Base's `AGENTS.md` and this file share 9,000,
  and the skeleton may use 75% (6,750). The largest render today (`service` with an image) is 6,042, so
  about 6,110 after; the budget test is the check.
- **Wiki** (new projects; these pages are project-owned): In-Depth-Configuration says the engine is
  interpose. Release-Process (template-owned) says interpose bumps come from tag-check.
- **Release:** `feat:` in template-python, a minor release. Not breaking: nothing an existing project
  runs changes until it migrates.
- **Rollback:** pin the previous tag; a project can return to its own copy at any time.

## Evidence from the first consumers (2026-11-02)

The two hand switches merged: metalayerlab/mitm-proxy#10 (`ef5d483`, released in mitm-proxy v0.2.0) and
metalayerlab/sluice#52 (`8352c53`). Both adopted interpose v0.1.0 in the shape described here. Checked
against the merged code:

- **The contract held.** Each `config.py` keeps `SETTINGS`, `CONFIG_ENV`, `Config` with `sources`,
  `ConfigError` and `load_config(path=None, environ=None)`, so `cli.py` and `gen-wiki.py` needed no change.
- **The migration lines are byte-identical** to the two blocks above, at the same place: the interpose pin
  is the first dependency, and the `[tool.hatch.metadata]` block follows `[tool.hatch.build.targets.wheel]`.
  `git` is on a `build:` line of `contrib/system-packages.txt` in both. Their next template update should
  merge cleanly.
- **Secrets confirm the rule.** mitm-proxy's `Config.proxy_auth` and `Config.ca_key` hold the `Secret`
  (`cast(Secret, ...)` in `load_config`), and `reveal()` is called where each is used: the auth callback
  and the CA's key PEM. Migration item 5 was fixed this way.
- **Case is the project's job.** `one_of` accepts a value in any case but returns it unchanged. It checks,
  it doesn't normalise. So both projects upper-case `log_level` in `load_config`, because the logging module
  wants upper case. Until metalayerlab/interpose#8 lands (`one_of` normalising to the canonical choice, or
  a transform hook on `Setting`), projects normalise case in `load_config`. The generated `load_config`
  does the same for any level-style setting it ships, as the sketch above does for `log_level`.
- **`check=` covers single-value project rules.** sluice has no cross-setting rule yet (`load_config`
  holds only a placeholder comment), so `secrets.dir` above is an example of where one would go, not a
  rule sluice has today. Its `env.expose` rules (variable names only, none of `SLUICE_*`) are a local
  function, `_exposable`, passed as `check=`. mitm-proxy does the same for `proxy.auth`, `intercept.hosts`
  and the middleware lists. Neither needed `load_config` for a rule about one value.

## Open questions

1. **Approve after 0002 is implemented?** Recommend yes: without it no generated project ever hears of a
   new interpose tag, and 0020's "Dependabot proposes interpose bumps" turned out false.
2. **Bring the dependency to existing projects before they migrate `config.py`?** Recommend yes: it's
   harmless unused, it's the first step of the migration anyway, and holding it back would need a Copier
   question or a second release.
3. **`cast` in the skeleton, or typed accessors in interpose first?** Recommend `cast` now and an interpose
   issue for `Resolved.str/int/bool/list/secret` (raising `TypeError` on the wrong kind); the skeleton
   switches when that is tagged.
4. **The Security page says secrets are read "from files only, never from the
   config file"**, but both engines accept a secret from the environment and the YAML file too. Fix the
   wording for new projects ("use `_FILE`"), or make interpose refuse other sources for `secret=True`?
   Recommend the wording: refusing is a breaking change in interpose for any deployment that sets the
   plain variable, which the template can't see, and interpose's call, not this record's.
5. **A check that a project's `config.py` still has its own engine?** Recommend no, as 0020 did: a
   project may keep its copy on purpose, and the migration prompt is enough.
