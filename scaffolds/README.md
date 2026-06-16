# QC Delegation Scaffolds

These scaffolds are copied into target repositories by `just install-qc-scaffold <language> <target>`.

They contain only repo-local command surfaces that delegate to the global QC stack in `~/ai-review-ci`. They must not carry generic QC tool configs, tool pins, hook scripts, or replacement lint/type/test implementations.
