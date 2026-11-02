# Migrating existing projects

One prompt per project, run in that project's own Claude Code session. Each one replaces `.copier-answers.yml`
with the stacked templates' answers files in one reviewed PR, after a 3-way merge of every template file
(the old template's version → the new templates', onto the project's).

| Project | From | Prompt |
|---|---|---|
| metalayerlab/interpose | project-template v0.1.18, library | [interpose.md](interpose.md) |
| metalayerlab/sluice | project-template v0.1.15, cli + image | [sluice.md](sluice.md) |
| metalayerlab/mitm-proxy | project-template v0.1.17, service + image | [mitm-proxy.md](mitm-proxy.md) |

They use template-base `v2.0.2`, template-python `v2.0.0` and template-container `v2.0.0`, the first releases of the overlays.

## After a template update

Changes a template update can't make, because the files are the project's (`src/`, `tests/`):

| Change | For | Prompt |
|---|---|---|
| `config.py` on interpose's settings engine (decision [0003](../decisions/0003-interpose-config.md)) | `service` and `cli` projects made before it | [interpose-config.md](interpose-config.md) |
