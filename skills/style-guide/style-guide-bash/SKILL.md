---
name: style-guide-bash
description: Load with the style guide when implementing or repairing Bash. Supplies Bash constructions for required inputs, explicit branching, failures, and proof.
---
# Bash Style Profile

Load the relevant foundation card from the [[style-guide/references/style-guide-index|style-guide index]], then apply these constructions:

- Start owned scripts with `set -euo pipefail`; validate required arguments, environment variables, files, and commands once at the boundary before work begins.
- Make operation modes explicit with subcommands or `case` over declared values. Do not infer modes from failed commands, missing files, or ambient shell state.
- Let unexpected command failures stop the script. Handle only a known, expected command status with an explicit branch and a stated domain meaning.
- Keep configuration in tracked files or explicit arguments. Do not silently default, discover, or continue after a missing critical dependency.
- Prove the real command path with controlled fixtures and observable outputs or side effects; do not use a no-crash check as proof.
