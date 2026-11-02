# Moving an existing project's `config.py` onto interpose

For a `service` or `cli` project made from template-python before decision 0003
([docs/decisions/0003](../decisions/0003-interpose-config.md)). Paste everything below the line into a Claude Code
session opened in that project. sluice (metalayerlab/sluice#52) and mitm-proxy (metalayerlab/mitm-proxy#10)
already did this by hand: read their `config.py` and `tests/unit/test_config.py` for the finished shape.

---

Move this project's settings engine out of `src/<package>/config.py` and onto interpose's
(`interpose.settings`, `interpose.secret`), as template-python's decision 0003 describes. `config.py` keeps
only what is this project's: SETTINGS, the Config dataclass, and load_config's cross-setting rules. Nothing a
user sees changes: the keys, variables, the `config` command's output and the wiki's settings table stay the
same. Work on a branch and open a PR; don't push to `main`.

## 1. Take the template update first

`config.py` and `tests/` are this project's, so `copier update` never rewrites them. The template update
that brings decision 0003 (template-python's CHANGELOG names it; template-update.yml opens it as a PR) adds:

- `"interpose @ git+https://github.com/metalayerlab/interpose@vX.Y.Z"` as the first dependency in
  `pyproject.toml`, and a `[tool.hatch.metadata]` block with `allow-direct-references = true` (hatchling
  refuses to build a direct reference without it);
- `git` in the Dockerfile's builder stage (`uv sync --frozen` fetches interpose with it);
- `ignore: interpose` in `dependabot.yml`'s `uv` entry (bumps come from `python-tag-check.yml`).

Merge that first. If this project already pins a newer interpose tag, the pin line conflicts: keep this
project's. If you added `git` to the `build:` line of `contrib/system-packages.txt` by hand, it can go now.

## 2. Record it

Write a short design record in `docs/design/` (from `0000-template.md`, with a line in its index): this
project now depends on interpose for its settings engine, why (template-python 0003: the copies drifted), and
what changes for users (the error texts in step 5; nothing else).

## 3. Rewrite `config.py`

Before you start, save what users see, to compare in step 5:

```sh
S=$(mktemp -d "${XDG_CACHE_HOME:-$HOME/.cache}/interpose-config.XXXXXX")
uv run <project> config -c /nonexistent > "$S/config-before.txt"
```

Then:

- Delete the engine: `Setting`, `Value`, `_lookup`, `_coerce`, `resolve`, `read_file` and the
  `ConfigError` class, and `import yaml` if nothing else in the module uses it.
- Import them instead: `from interpose.settings import ConfigError, Setting, Settings` (plus `one_of`,
  `port`, `positive`, `non_negative` as the checks need, and `from interpose.secret import Secret` if a
  setting is secret).
- `SETTINGS = Settings(ENV_PREFIX, (...same Setting(...) entries...), default_path=DEFAULT_CONFIG_PATH)`
  and `CONFIG_ENV = SETTINGS.config_env`. Keep every key, default and help text as it is.
- Move each rule about one value into that setting's `check=`: the log level becomes
  `check=one_of(*LOG_LEVELS)`, the port `check=port`. A project rule is a function that raises
  `ValueError` with the reason. Only a rule that spans settings stays in `load_config`.
- `load_config(path=None, environ=None)` becomes `resolved = SETTINGS.resolve(path, environ)`, the
  cross-setting rules, then `Config(...)` from `resolved.values` with `sources=dict(resolved.sources)`.
  Narrow each value with `cast(str, ...)`, `cast(int, ...)` and so on, never `str(...)`.
- `one_of` accepts any case and keeps the case it was given, so upper-case the log level (and any other
  level-style setting) in `load_config`: `log_level=cast(str, v["log_level"]).upper()`. That stays until
  interpose#8 makes `one_of` return the declared spelling.
- **A `secret=True` setting resolves to a `Secret`.** `str()`, `repr()` and an f-string give `********`,
  so a `str(values["x"])` that worked before now sends `********`, silently. Hold it in `Config` as
  `Secret` (`cast(Secret, ...)`) and call `.reveal()` where it's used: a header, a connection string, a
  key file. Search for every use of each secret field.
- Keep the module docstring's contract: it exports SETTINGS, CONFIG_ENV, Config (with `sources`),
  ConfigError and `load_config(path=None, environ=None)`. `cli.py` and `scripts/gen-wiki.py` (both
  template-owned) use only these.

interpose refuses some declarations at import with a `ValueError`: a secret that isn't a `str` setting, a
list setting whose default isn't `""`, two settings that share a variable (`a.b` and `a_b`), and a key part
YAML doesn't read as a string (`on`, `no`, `null`). Rename or fix any it names, and record a renamed key as
breaking.

## 4. Rewrite the tests

- Delete the engine's tests (`_coerce`, `resolve`, `read_file`, coercion of bools, ints, lists): interpose
  tests those.
- Keep the project's: each source end to end, the defaults, every `check=` and cross-setting rule, a
  non-mapping file, a list setting's split. Add one that pins `[(s.key, s.env) for s in SETTINGS]`, so a
  renamed variable fails a test.
- Messages that changed: invalid YAML is `cannot parse <path> at line L, column C: ...` (was `cannot read`);
  a coercion error ends `(from <source>)`; `one_of`'s is `expected one of A, B, got 'x'`.
- `tests/unit/test_cli.py` builds a `Setting` to test masking: import it from `interpose.settings`.
- A secret setting: test that `load_config` gives a `Secret`, that `str()` of it is `********`, and that
  `.reveal()` gives the value from its `_FILE`.

## 5. Check nothing users see changed

```sh
uv run <project> config -c /nonexistent | diff "$S/config-before.txt" -   # no output
uv run scripts/gen-wiki.py --check                                       # the settings table is unchanged
sh scripts/checks.sh
uv sync --locked && uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
docker build .                                                           # if there's a Dockerfile
rm -rf "$S"
```

Commit as `refactor: config.py on interpose's settings engine` (`feat:` if a key or variable changed) and
open the PR. In its body, list the settings moved to `check=`, each secret now held as `Secret`, and the
error texts that changed.
