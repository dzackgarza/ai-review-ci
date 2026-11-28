# Research container

## Task and completion conditions

Provide one reusable Sage/CAS development environment for this host and CI.
The image owns the Sage fork, language runtimes, research dependencies and Git
checkouts. Host editors and Git commands access the same writable checkouts
through links. Existing branches, worktrees and local files survive the move.

| Requirement | Acceptance |
| --- | --- |
| Sage fork | Editable `/sage` checkout, compiled with its Meson build, running through its own Python environment |
| CAS tools | Working Julia, Oscar/Hecke, GAP, Macaulay2 and Singular, including the Sage Julia bridge |
| Research repositories | The image's `docker/research-repositories.txt` covers the relevant research sources; installed packages load from these checkouts |
| Host development | Ordinary host paths reach container source; edits are visible to the runtime; Git can commit and publish from those paths |
| Data preservation | Existing local branches, worktrees and files remain accessible after relocation |
| Shared builds | Consumers reuse the published image; Sage builds run in CI with reusable compiler/image caches |
| Local checks | Cheap configuration and launch checks run before a long CI build |
| Host operation | Rootless Docker starts the environment and the host commands reach its tools |

## Use the image

The shared Linux amd64 image is `ghcr.io/dzackgarza/sage:develop`. It includes
Lean/Lake/elan, Sage with mypy and pytest, GAP, Julia with Oscar/Hecke,
Macaulay2, Singular, Normaliz, polymake, and CoxIter.

Pull it and open a shell with Docker:

```bash
docker pull ghcr.io/dzackgarza/sage:develop
docker run --rm -it ghcr.io/dzackgarza/sage:develop bash
```

Inside the image, Sage's Python is `/sage/.venv/bin/python`, the Sage source
is `/sage`, and the research checkouts are under `/repos`. For example:

```bash
docker run --rm ghcr.io/dzackgarza/sage:develop python -c 'from sage.all import QQ, matrix; assert matrix(QQ, [[2, 1], [1, 2]]).det() == 3'
```

For CI, use the image as the job container; pin an immutable digest for
reproducible runs. See the working
[GitHub Actions consumer](https://github.com/dzackgarza/sage/blob/develop/.github/workflows/research-image-consumer.yml).

On the configured workstation, run `sage-docker-update` to pull the image and
start or update `sage-research`. Use the host commands listed below, including
`sage-docker-python` for Sage's Python. The launcher retains source and Julia
volumes across updates. Host launcher installation is owned by
[`just install-sage-launchers`](justfile) in this repository.

## Set up another host

A host runs the same environment once these steps hold. Remove what the image
replaces before the pull: a host copy of Sage, GAP, Julia, Lean or the research
checkouts beside the image doubles the disk use, and the image (40 GB unpacked)
plus its volumes (about 10 GB) need room on their own.

1. Inventory the host. List host installs that duplicate the image
   (`docker/research-environment.Dockerfile` in `dzackgarza/sage` names them),
   and for each research checkout in `~/gitclones` its unpushed commits,
   uncommitted changes and linked worktrees. Find who owns a directory before
   calling it unused: `pacman -Qo PATH` (an AUR package can own a whole `/opt`
   tree that `/usr/bin` links into).
2. Remove the host duplicates.
3. Install rootless Docker into `~/bin` with the
   [rootless installer](https://docs.docker.com/engine/security/rootless/)
   (`FORCE_ROOTLESS_INSTALL=1` when a rootful daemon also runs). The installer
   switches the CLI to its `rootless` context; switch back with
   `docker context use default` when the rootful daemon's containers still
   matter. The launcher reaches the rootless daemon through `DOCKER_HOST` on its
   own.
4. Select the overlay2 store before the first pull, as rack does, and restart
   the daemon (`systemctl --user restart docker`):

   ```json
   { "features": { "containerd-snapshotter": false } }
   ```

   in `~/.config/docker/daemon.json`. The containerd store keeps the
   compressed layers (14 GB) beside the unpacked image.
5. `just install-sage-launchers`, then `sage-docker-update`. On a laptop the
   pull may drop; run it again, and finished layers are kept. The update creates
   the container and the volumes, records the image revision for a newly
   created `sage-tree` volume, and then stops at the first real directory in
   `~/gitclones` that has a volume checkout's name. The revision marker
   prevents a subsequent update with the same image from copying the build
   products again.
6. Move each such checkout into
   `~/.local/share/docker/volumes/sage-repos/_data/NAME` in place of the image's
   copy (`mv` keeps its branches, refs and local files), then run
   `git worktree repair` for its linked worktrees. Fetch branches that exist only
   in a Dropbox copy into the volume checkout; leave the Dropbox copy where it
   is, because moving it out of Dropbox deletes it on every synced machine.
   The update checks only `~/gitclones`; a research checkout elsewhere, such
   as `~/research`, moves the same way and is replaced by a link to its volume
   checkout. Ignored files that a host environment generated, such as
   `sage-julia-bridge`'s `julia_env/Manifest.toml`, come from the image's copy.
7. Run `sage-docker-update` again; it links every volume checkout into
   `~/gitclones`. Then run the computations of **Verified computations** on
   the host commands.

## Host workspace

The `sage-research` runtime mounts these persistent volumes:

| Volume | Container path | Content |
| --- | --- | --- |
| `sage-tree` | `/sage` | Sage checkout and build environment |
| `sage-repos` | `/repos` | Research checkouts, their branches, linked worktrees and local files |
| `sage-julia` | `/root/.julia` | Writable Julia packages, global environments and compiled caches |

`~/gitclones/sage` and the research links under `~/gitclones` reach these
volumes directly. Existing `~/research`, `~/sage-julia-bridge` and
`~/sage-mypy-plugin` paths also reach their relocated checkouts. The move
preserved the original directory identities, HEADs, refs and local changes.

Host commands `sage`, `sage-docker-python`, `sage-docker-preparse`, `jupyter`,
`julia`, `gap`, `M2`, `Singular`, `coxiter`, `normaliz`, `polymake`, `lean`, `lake` and
`elan` run in this runtime. `sage-docker-update` refreshes the runtime while
retaining the volumes. Python runs from `/sage/.venv`; Julia uses its writable
depot before the image's `/opt/julia-depot`. Its initial global environment
comes from the image, and subsequent package changes belong to the volume.

## Launcher behaviour

[scripts/sage-docker](scripts/sage-docker) is one script; the name it is
called by selects the command.

- **Rootless Docker.** The launcher talks to the rootless daemon at
  `unix:///run/user/$UID/docker.sock` through `$HOME/bin/docker`. Root in the
  container is the host user, so files written under `/home/dzack` keep their
  owner, and the image's own `HOME` (`/root`), with the Julia and Catlab
  environments the image build resolved, is used as built.
- **Checkouts in volumes.** The fork is the `sage-tree` volume at `/sage` and
  every research repository is in the `sage-repos` volume under `/repos`.
  Docker fills a named volume from the image only when it creates the volume.
  The host reaches the checkouts through `~/gitclones` symlinks into
  `~/.local/share/docker/volumes`, so agents edit, commit and push them with
  ordinary tools and the container runs what they edit. A real directory in
  `~/gitclones` with the name of a volume checkout stops the update: its work
  must move into the volume checkout first. A link whose volume checkout is
  gone is removed.
- **Work directory.** A command started inside a volume's host directory runs
  in that volume's container path: `~/gitclones/lean-cas-dsl` runs in
  `/repos/lean-cas-dsl`. Relative paths in a checkout, such as a Lean
  `packagesDir` of `../../.local/share/lean/...`, then resolve as the image
  build resolved them. Other directories keep their host path through the
  `/home/dzack` mount.
- **Jupyter.** The container publishes `127.0.0.1:8888`, and the host
  `jupyter` command runs Jupyter in the container with the host's
  `~/.jupyter` as its configuration directory. `jupyter lab`, `jupyter server`
  and `jupyter notebook` get `--ip=0.0.0.0 --port=8888 --no-browser
  --allow-root` after the caller's arguments, so the server listens where the
  published port reaches it; a different port is overridden. The kernels are
  the image's (`sagemath`, `julia`, `python3`). No host process may hold port
  8888 when the container is created.
- **Container configuration.** The container carries a hash of its run
  options as the `sage-docker.config` label. An update recreates a container
  whose label differs, so a change to the mounts, environment or published
  ports reaches hosts with their next update.
- **Is the local image current?** The update asks the registry for the tag's
  index digest (`Docker-Content-Digest` of the manifest request) and compares
  it with the local image's `RepoDigests`. Both the overlay2 store and the
  containerd store record the index digest there. `docker image inspect
  --format '{{.Descriptor.Digest}}'` is not used: the overlay2 store has no
  `Descriptor` field. An image that is not current is removed before the pull,
  together with its container, so an update never holds two images on disk.
- **The `sage-tree` volume after a new image.** The volume shadows the image's
  `/sage` and still holds the previous image's checkout, `.venv` and
  `builddir`. The update fast-forwards the checkout to the image's
  `org.opencontainers.image.revision` and takes `.venv`, `builddir` and the
  build's untracked records (`.research-revisions`, `.spinor-base-revision`,
  `.spinor-source-revision`) from the image. The dirty-checkout check excludes
  those records. Any other uncommitted change, or a checkout that cannot
  fast-forward, stops the update.
- **Julia.** The shared environments in `/root/.julia/environments` name the
  packages that the image depot holds, so each update copies them from
  `/opt/julia-depot`. `JULIA_DEPOT_PATH` puts the writable volume depot in front
  of the read-only image depot; its trailing empty entry keeps the stdlib depot.
- **Termination.** Killing a `docker exec` client leaves its process running in
  the container. The command therefore runs as the leader of its own process
  group and records its pid, and the launcher kills that group when it is
  terminated or exits.

## Verified computations

| Consumer | Expected result verified on the host |
| --- | --- |
| Sage | Determinant of `[[2,1],[1,2]]` is `3` |
| GAP through Sage | `Size(SymmetricGroup(3))` is `6` |
| Singular and Macaulay2 through Sage | `1+1` is `2` |
| Oscar/Hecke | The number field defined by `x^2-2` has degree `2`; its generator squares to `2` |
| Sage Julia bridge | `1 // 2` converts to Sage's exact rational; Oscar's `ZZ(2)^10` converts to `1024` |
| Research session preamble | `ZZ(2)**10` is `1024` |
| Lean and Lake | Both select the image's Lean `4.37.0-rc1` toolchain; from `~/gitclones/lean-cas-dsl`, `lake env lean` imports the shared Mathlib |

## Deployed image and verification

[Image build 41217622692](https://github.com/dzackgarza/sage/actions/runs/41217622692)
passed for source `b0cd7d86e21eb450ed90e4c83707920e1d5d429a`.

| Image object | Immutable digest |
| --- | --- |
| OCI index | `sha256:ccdea4a52158c8fea4ef46b80dcf4cecd90ef0b61afa467f9541c6c658eeff09` |
| Linux amd64 manifest | `sha256:c3a9f1637d43b727ab2b24c0ccf1bc9ee513a08a02094d20221065ef2d8643dd` |

The image sets `JULIA_CPU_TARGET=generic` before precompilation, following the
[Julia package-image configuration](https://docs.julialang.org/en/v1.12/manual/environment-variables/#JULIA_CPU_TARGET).
It initializes the bridge's own Julia project, includes every Git source in
the research dependency lock as a checkout, makes Sage's Python the default,
and sets the default Lean toolchain. Its build checks passed.

The host runs this image. The changed-image update preserved the source-directory
identities, original branches and refs, linked worktrees, local changes, and the
writable Julia environment. The computations above passed after deployment.
A fresh container, with no host Julia volume, loaded JSON/Oscar using
`julia --compiled-modules=strict` and verified the quadratic number-field example.
The persistent Julia environment and Sage Julia bridge also passed after deployment.
[Fresh CI consumer 41224747377](https://github.com/dzackgarza/sage/actions/runs/41224747377)
passed default Python and an exact rational determinant against the immutable
amd64 manifest on a fresh hosted runner.

The launcher is [scripts/sage-docker](scripts/sage-docker). The image source is
the `develop` branch of `dzackgarza/sage`. Its
`docker/research-environment-check.py` checks the built environment; publication
alone does not establish host deployment or preservation of local work.
