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

## Current required work

Deploy the image published by Sage workflow run `41149687627`, verify its
runtime and source paths, move existing local checkouts into its persistent
storage, and connect the host paths. Verify each completion condition above.
The running container at the start of this migration predates that image.

The launcher is [scripts/sage-docker](scripts/sage-docker). The image source is
the `develop` branch of `dzackgarza/sage`. Its
`docker/research-environment-check.py` checks the built environment; publication
alone does not establish host deployment or preservation of local work.
