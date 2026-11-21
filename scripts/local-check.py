#!/usr/bin/env python3
"""Parse the Python, JSON and TOML files a commit stages or a push publishes.

Usage: local-check.py staged|push. Reads blobs from Git, never the working tree.
The pre-push hook sets AI_REVIEW_CI_PRE_PUSH_REMOTE and leaves the outgoing refs
on stdin; a manual push check compares HEAD with its tracked upstream.
"""

import ast
import json
import os
import subprocess
import sys
import tomllib

MODE = sys.argv[1]
REMOTE = os.environ.get("AI_REVIEW_CI_PRE_PUSH_REMOTE")
SYNTAX_SUFFIXES = (".py", ".pyi", ".json", ".toml")


def git(*args):
	return subprocess.run(["git", *args], check=True, stdout=subprocess.PIPE).stdout


def commit_oid(oid):
	"""Peel a ref to a commit; None for a missing, deleted or non-commit ref."""
	if not oid or set(oid) == {"0"}:
		return None
	# Missing upstreams are normal on new branches; probing them must never
	# print Git's fatal diagnostic during an otherwise successful check.
	result = subprocess.run(
		["git", "rev-parse", "--verify", oid + "^" + "{" + "commit" + "}"],
		stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
	)
	return result.stdout.decode().strip() if result.returncode == 0 else None


def push_base(commit, remote_oid, remote):
	"""A local base for the push, found without fetching or walking history."""
	if remote_oid and (base := commit_oid(remote_oid)):
		return base
	if remote_oid is None and (upstream := commit_oid("@{upstream}")):
		# A manual push check compares with the branch's tracked remote, so an
		# already-published feature branch is not re-audited from main.
		return upstream
	for candidate in (
		f"refs/remotes/{remote}/HEAD",
		f"refs/remotes/{remote}/main",
		f"refs/remotes/{remote}/master",
		"refs/remotes/origin/main",
		"refs/heads/main",
	):
		if candidate_oid := commit_oid(candidate):
			try:
				base = git("merge-base", commit, candidate_oid).decode().strip()
			except subprocess.CalledProcessError:
				continue
			if base != commit:
				return base
	# With no known remote base, the newest commit keeps an initial
	# publication bounded; CI checks the complete tree.
	return commit_oid(f"{commit}^")


def push_changes():
	"""Files changed by every outgoing ref, read from the committed trees."""
	if REMOTE is None:
		refs = [(commit, None) for commit in [commit_oid("HEAD")] if commit]
	else:
		refs = []
		for line in sys.stdin.buffer:
			parts = line.decode("utf-8", errors="surrogateescape").split()
			if len(parts) != 4:
				raise ValueError("Malformed Git pre-push ref update")
			_, local_oid, _, remote_oid = parts
			if commit := commit_oid(local_oid):
				refs.append((commit, remote_oid))
	changes = []
	for commit, remote_oid in refs:
		base = push_base(commit, remote_oid, REMOTE or "origin")
		if base is None:
			names = git("ls-tree", "-r", "--name-only", "-z", commit)
		else:
			names = git("diff", "--name-only", "--diff-filter=ACMR", "-z", base, commit)
		changes.extend((os.fsdecode(raw), commit) for raw in names.split(b"\0") if raw)
	return changes


def parse(path, content):
	text = content.decode("utf-8-sig")
	if path.endswith((".py", ".pyi")):
		ast.parse(text, filename=path)
	elif path.endswith(".json"):
		json.loads(text)
	elif path.endswith(".toml"):
		tomllib.loads(text)


try:
	if MODE == "staged":
		# GIT_INDEX_FILE is kept: `git commit --only` supplies a temporary index.
		names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
		changes = [(os.fsdecode(raw), "index") for raw in names.split(b"\0") if raw]
	else:
		changes = push_changes()
except (ValueError, UnicodeError, subprocess.CalledProcessError) as error:
	sys.exit(f"Cannot inspect candidate source: {error}")

checked = errors = 0
for path, version in dict.fromkeys(changes):
	if not path.endswith(SYNTAX_SUFFIXES):
		continue
	try:
		parse(path, git("show", f":{path}" if version == "index" else f"{version}:{path}"))
	except (SyntaxError, UnicodeError, json.JSONDecodeError, tomllib.TOMLDecodeError, subprocess.CalledProcessError) as error:
		print(f"{path}: {error}", file=sys.stderr)
		errors += 1
	checked += 1
if errors:
	sys.exit(1)
print(f"{'Push' if MODE == 'push' else 'Staged'} syntax: {checked} file(s) checked; no errors.")
