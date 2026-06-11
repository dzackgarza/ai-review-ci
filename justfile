qc-type := "python"

# Parse-check every infrastructure source: workflow YAML, runner justfile, shell wrappers
check:
    python3 -c "import ast, pathlib; [ast.parse(p.read_text()) for p in pathlib.Path('src').rglob('*.py')]; [ast.parse(p.read_text()) for p in pathlib.Path('tests').rglob('*.py')]"
    python3 -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/_review.yml').read_text())"
    just -f ci/runner.just --list >/dev/null
    bash -n ci/private/submit-candidate
    sh -n ci/reviewer_home/bin/submit-candidate

# Full quality gate: routes through the global QC chain for Python projects
test:
    just -f {{home_directory()}}/ai/quality-control/justfile-python -d . test

# Install the trigger workflows into a target repo
install target=".":
    uvx --from . ai-review-ci install --target {{target}}
