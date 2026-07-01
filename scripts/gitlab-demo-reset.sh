#!/bin/bash
# Resets the GitLab demo state for the next run
set -e

GITLAB_URL="http://gitlab.local"
PROJECT_ID=2
GITLAB_PAT=$(grep GITLAB_PAT /home/scarolan/git_repos/harness-demo/.env | cut -d= -f2)

echo "=== Resetting GitLab Demo ==="

# Close any open MRs on the demo branch
MR_IDS=$(curl -s -H "PRIVATE-TOKEN: $GITLAB_PAT" \
  "$GITLAB_URL/api/v4/projects/$PROJECT_ID/merge_requests?source_branch=demo/user-search&state=opened" | \
  python3 -c "import sys,json; [print(mr['iid']) for mr in json.load(sys.stdin)]" 2>/dev/null)

for MR_ID in $MR_IDS; do
  curl -s -X PUT \
    -H "PRIVATE-TOKEN: $GITLAB_PAT" \
    -H "Content-Type: application/json" \
    -d '{"state_event": "close"}' \
    "$GITLAB_URL/api/v4/projects/$PROJECT_ID/merge_requests/$MR_ID" > /dev/null
  echo "Closed MR !$MR_ID"
done

# Switch to main and clean up
git checkout main
git pull gitlab main 2>/dev/null || true

# Delete demo branch locally and on GitLab
git branch -D demo/user-search 2>/dev/null || true
git push gitlab --delete demo/user-search 2>/dev/null || true

echo "=== GitLab demo reset complete. ==="
