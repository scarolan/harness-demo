#!/bin/bash
# Resets demo state — run between demo sessions
set -e

echo "=== Resetting Demo ==="

# Warn before discarding anything on the demo branch that isn't the demo itself.
# The branch is force-deleted below, so real work committed here would be lost.
if git rev-parse --verify -q demo/user-search >/dev/null; then
    EXTRA=$(git log --oneline main..demo/user-search 2>/dev/null \
        | grep -viE "Add user search endpoint|Fix SQL injection" || true)
    if [ -n "$EXTRA" ]; then
        echo ""
        echo "WARNING: demo/user-search has commits that are not on main and not"
        echo "         part of the demo. Deleting the branch would discard them:"
        echo "$EXTRA" | sed 's/^/           /'
        echo ""
        printf "Cherry-pick them to main first. Delete anyway? [y/N] "
        read -r REPLY
        case "$REPLY" in
            [yY]) echo "Proceeding — commits above will be unreachable (recover via git reflog)." ;;
            *) echo "Aborted. Nothing deleted."; exit 1 ;;
        esac
    fi
fi

# Close any open demo PRs
for pr in $(gh pr list --head demo/user-search --json number -q '.[].number' 2>/dev/null); do
    echo "Closing PR #$pr"
    gh pr close "$pr" --delete-branch 2>/dev/null || true
done

# Clean up local branch
git checkout main
git pull
git branch -D demo/user-search 2>/dev/null || true

# Delete remote branch if it still exists
git push origin --delete demo/user-search 2>/dev/null || true

# Restore dev to main's image. A PR build used to deploy the branch, so dev could be
# left running code from a PR that just got closed.
MAIN_SHA=$(git rev-parse --short=7 HEAD)
WANT="carolanio/harness-demo:$MAIN_SHA"
LIVE=$(kubectl -n harness-demo get deploy harness-demo \
    -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo "")

if [ -z "$LIVE" ]; then
    echo "No harness-demo deployment found — skipping image restore."
elif [ "${LIVE##*/}" = "${WANT##*/}" ]; then
    echo "Dev already running main ($MAIN_SHA) — no restore needed."
else
    echo "Dev is running ${LIVE##*/}, restoring to $MAIN_SHA"
    kubectl -n harness-demo set image deployment/harness-demo "harness-demo=$WANT"
    if ! kubectl -n harness-demo rollout status deployment/harness-demo --timeout=90s; then
        # Usually means no image was ever pushed for this commit (e.g. main was never
        # built). Roll back so the demo starts on something that actually runs.
        echo ""
        echo "WARNING: rollout did not complete — $MAIN_SHA may not exist in the registry."
        echo "         Rolling back to ${LIVE##*/}."
        kubectl -n harness-demo rollout undo deployment/harness-demo || true
        kubectl -n harness-demo rollout status deployment/harness-demo --timeout=90s || true
    fi
fi

echo ""
echo "=== Demo reset complete. Run ./scripts/demo-start.sh to begin. ==="
