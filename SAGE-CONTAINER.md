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

Host commands `sage`, `sage-docker-python`, `sage-docker-preparse`, `julia`,
`gap`, `M2`, `Singular`, `coxiter`, `normaliz`, `polymake`, `lean`, `lake` and
`elan` run in this runtime. `sage-docker-update` refreshes the runtime while
retaining the volumes. Python runs from `/sage/.venv`; Julia uses its writable
depot before the image's `/opt/julia-depot`. Its initial global environment
comes from the image, and subsequent package changes belong to the volume.

## Verified computations

| Consumer | Expected result verified on the host |
| --- | --- |
| Sage | Determinant of `[[2,1],[1,2]]` is `3` |
| GAP through Sage | `Size(SymmetricGroup(3))` is `6` |
| Singular and Macaulay2 through Sage | `1+1` is `2` |
| Oscar/Hecke | The number field defined by `x^2-2` has degree `2`; its generator squares to `2` |
| Sage Julia bridge | `1 // 2` converts to Sage's exact rational; Oscar's `ZZ(2)^10` converts to `1024` |
| Research session preamble | `ZZ(2)**10` is `1024` |
| Lean and Lake | Both select the installed Lean `4.33.0` toolchain |

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
