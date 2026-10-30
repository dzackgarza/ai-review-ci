#!/usr/bin/env bash
# Usage: with-central-biome-config.sh CONFIG COMMAND...
# Run COMMAND with CONFIG installed as the project-root biome.json, then remove it.
# Biome applies a --config-path file's language options (css.parser.tailwindDirectives)
# only to files under that file's directory, so the central config must sit at the root.
set -euo pipefail
config="$1"
shift
for name in biome.json biome.jsonc .biome.json .biome.jsonc; do
	if [ -e "$name" ] || [ -L "$name" ]; then
		echo "ERROR: $name exists in the project; QC configuration is central (ai-review-ci #292)."
		exit 1
	fi
done
trap 'rm -f biome.json' EXIT
cp "$config" biome.json
"$@"
