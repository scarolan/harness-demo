#!/bin/bash
# Resets demo state — run between demo sessions
set -e

echo "=== Resetting Demo ==="

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

echo ""
echo "=== Demo reset complete. Run ./scripts/demo-start.sh to begin. ==="
