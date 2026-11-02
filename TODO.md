# TODO

template-python's own outstanding work. Bugs and features with discussion belong in GitHub issues; this file
is for what maintainers (and their AI assistants) should know at a glance.

## Open

- The generated `config.py` narrows values with `cast()`: switch to interpose's typed accessors once [metalayerlab/interpose#13](https://github.com/metalayerlab/interpose/issues/13) is tagged, and drop `load_config`'s `log_level` `.upper()` once [interpose#8](https://github.com/metalayerlab/interpose/issues/8) is (decision 0003)

## Decided against (don't re-propose without reading this first)

<!-- One line each: the idea, why not, and a link to the issue, PR or design record. Carried from
project-template v0.1.23's TODO.md; its records are in its docs/design/. -->

- A project-owned `contrib/image-extras.txt` for the image's Python extras: a Copier answer renders them with no parsing and no conflicts (project-template [0012](https://github.com/metalayerlab/project-template/blob/v0.1.23/docs/design/0012-image-extras.md))
- A `test:` list in `contrib/system-packages.txt` for the integration job: it installs the `runtime:` list too (project-template [0017](https://github.com/metalayerlab/project-template/blob/v0.1.23/docs/design/0017-integration-ci-job.md))
- A seeded project-owned `integration.yml` workflow: it would never receive fixes, so the job is in the template-owned `stack-ci.yml` (project-template [0017](https://github.com/metalayerlab/project-template/blob/v0.1.23/docs/design/0017-integration-ci-job.md))
- Reusing `image_extras` for the integration job, or one list-valued `integration_ci`: the image and the tests can need different extras, and "off" needs its own value (project-template [0017](https://github.com/metalayerlab/project-template/blob/v0.1.23/docs/design/0017-integration-ci-job.md))
- Integration tests inside the Test job's matrix: they would count towards the coverage floor (project-template [0017](https://github.com/metalayerlab/project-template/blob/v0.1.23/docs/design/0017-integration-ci-job.md))
