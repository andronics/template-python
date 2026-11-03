# 0009: A service's working directory is its state directory

<!-- Add a line for this record to the index in docs/decisions/README.md (CI checks). -->

Status: Proposed
Date: 2026-11-03
Authors: Stephen Cox

## Context

The Dockerfile's runtime stage sets no `WORKDIR` (the builder's `/build` doesn't carry over), so a
`kind: service` container runs in `/`, and so does the systemd unit, which sets no `WorkingDirectory=`. The
skeleton never uses a relative path: config is `/etc/<project>/config.yaml`, state is `state_dir`
(default `/var/lib/<project>`). Code brought in by a migration does. qbt-rules' staged migration
(template-python v2.4.0) kept its Flask server for a few steps, and that code resolves `./config`; in `/`
that is `/config`, the old image's volume, so a container started with the old mount silently read the old
config instead of failing.

## Decision

- **`kind: service` images:** `WORKDIR /var/lib/<project>` in the runtime stage, after the directory is
  created and given to the `<project>` user, before the healthcheck and entrypoint.
- **The systemd unit:** `WorkingDirectory=/var/lib/<project>` (the `StateDirectory=`, created before the
  service starts).
- **`kind: cli` images** keep no `WORKDIR`: they have no state directory, and a one-off run picks its own
  directory (`docker run -w`).

The state directory, not the config directory: it is the one directory the service owns and can write
(the root filesystem is read-only in template-container's manifests, and `/etc/<project>` is mounted
read-only), and it is always present: the image creates it, the volume or `emptyDir` is mounted there, and
the entrypoint gives it to `PUID:PGID`. A relative path now lands in the service's own volume, never at the
root of the filesystem. `state_dir` stays the setting code should use; the working directory is a safety
net, not an interface, and it stays `/var/lib/<project>` when `<PREFIX>STATE_DIR` moves the state.

## Alternatives considered

- **`/etc/<project>`.** Read-only, and a relative write fails there just as in `/`. A legacy `./config`
  would resolve to `/etc/<project>/config`, which is neither layout.
- **`/home/<project>` (the user's home).** Not a volume, so anything written there is lost on restart,
  and under the read-only root it isn't writable either.
- **Leave it to each project.** The Dockerfile is template-owned, so a project can't add one without a
  diverging copy.

## Consequences

- Existing services (checked 2026-11-03): trackie and mitm-proxy use absolute paths only (trackie's
  legacy `/config/config.yml` and `/config/state` are absolute), so nothing they read or write moves. sluice
  is `kind: cli` and unchanged. None has `contrib: systemd`, and the unit is a new project's file anyway.
- `docker exec <c> <project> ...` also starts in the state directory.
- A migrated service whose legacy code resolves paths relative to the working directory now finds them
  in `/var/lib/<project>` (where qbt-rules keeps its legacy files until its config port lands) and no
  longer in `/`.
- Rollback: drop the line; nothing else depends on it.

## Open questions

None.
