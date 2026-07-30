"""Post a Harness build status back to the GitHub commit status API.

Uses only the standard library so the pipeline step needs no pip install.

Environment:
  GITHUB_TOKEN   (required) PAT with repo:status scope
  GITHUB_REPO    (required) owner/repo, e.g. scarolan/harness-demo
  STATUS_STATE   (required) pending | success | failure | error
  STATUS_CONTEXT (required) the check name GitHub displays
  STATUS_DESC    short description shown next to the check
  TARGET_URL     link the check points at (the Harness execution)
  PR_NUMBER      set on PR builds; used to resolve the PR head SHA
  COMMIT_SHA     fallback SHA when PR_NUMBER is absent
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"


def unresolved(value):
    """Harness leaves the literal expression behind when a step it references failed."""
    return not value or value.startswith("<+") or value == "null"


def clean(value, fallback=""):
    value = (value or "").strip()
    return fallback if unresolved(value) else value


def call(path, token, data=None):
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(data).encode() if data is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def resolve_sha(repo, pr_number, commit_sha, token):
    """GitHub evaluates required checks against the PR head SHA, not the merge ref."""
    if not unresolved(pr_number):
        pr = call(f"/repos/{repo}/pulls/{pr_number}", token)
        return pr["head"]["sha"], f"PR #{pr_number} head"

    if not unresolved(commit_sha):
        return commit_sha, "codebase.commitSha"

    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    if not sha:
        raise SystemExit("ERROR: could not determine a commit SHA to report against")
    return sha, "git rev-parse HEAD"


def main():
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = clean(os.environ.get("GITHUB_REPO"))
    state = clean(os.environ.get("STATUS_STATE"))
    context = clean(os.environ.get("STATUS_CONTEXT"))

    missing = [
        name
        for name, val in [
            ("GITHUB_TOKEN", token),
            ("GITHUB_REPO", repo),
            ("STATUS_STATE", state),
            ("STATUS_CONTEXT", context),
        ]
        if not val
    ]
    if missing:
        raise SystemExit(f"ERROR: missing required env: {', '.join(missing)}")

    description = clean(os.environ.get("STATUS_DESC"), "Harness pipeline")
    # GitHub truncates descriptions over 140 chars.
    description = description[:137] + "..." if len(description) > 140 else description

    sha, source = resolve_sha(
        repo,
        clean(os.environ.get("PR_NUMBER")),
        clean(os.environ.get("COMMIT_SHA")),
        token,
    )

    payload = {"state": state, "context": context, "description": description}
    target_url = clean(os.environ.get("TARGET_URL"))
    if target_url:
        payload["target_url"] = target_url

    print(f"Posting '{state}' to {repo}@{sha[:7]} (from {source})")
    print(f"  context     : {context}")
    print(f"  description : {description}")

    try:
        call(f"/repos/{repo}/statuses/{sha}", token, payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:300]
        raise SystemExit(f"ERROR: GitHub returned {exc.code}: {body}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"ERROR: could not reach GitHub: {exc.reason}")

    print("GitHub commit status updated.")


if __name__ == "__main__":
    main()
