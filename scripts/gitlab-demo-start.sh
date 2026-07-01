#!/bin/bash
# Creates a merge request on GitLab with a SQL injection vulnerability
set -e

GITLAB_URL="http://gitlab.local"
PROJECT_ID=2
GITLAB_PAT=$(grep GITLAB_PAT /home/scarolan/git_repos/harness-demo/.env | cut -d= -f2)

echo "=== Starting GitLab Demo ==="

# Make sure we're on main and synced
git checkout main
git pull gitlab main 2>/dev/null || true

# Clean up any previous demo branch
git branch -D demo/user-search 2>/dev/null || true
git push gitlab --delete demo/user-search 2>/dev/null || true

# Create fresh branch
git checkout -b demo/user-search

# Add vulnerable search endpoint
cat >> app/main.py << 'PYEOF'

@app.get("/api/search")
def search_users(query: str):
    import sqlite3
    conn = sqlite3.connect("users.db")
    cursor = conn.execute(f"SELECT * FROM users WHERE name LIKE '%{query}%'")
    results = cursor.fetchall()
    conn.close()
    return {"results": results}
PYEOF

git add app/main.py
git commit -m "Add user search endpoint"
git push -u gitlab demo/user-search

# Create merge request via GitLab API
MR_URL=$(curl -s -X POST \
  -H "PRIVATE-TOKEN: $GITLAB_PAT" \
  -H "Content-Type: application/json" \
  -d "{
    \"source_branch\": \"demo/user-search\",
    \"target_branch\": \"main\",
    \"title\": \"Add user search endpoint\",
    \"description\": \"Search users by name for the frontend team.\"
  }" \
  "$GITLAB_URL/api/v4/projects/$PROJECT_ID/merge_requests" | python3 -c "
import sys, json
mr = json.load(sys.stdin)
print(mr.get('web_url', 'ERROR'))
")

echo ""
echo "=== MR created: $MR_URL ==="
echo "=== Switch to Harness UI to watch the review. ==="
