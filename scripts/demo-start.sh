#!/bin/bash
# Creates a PR with a SQL injection vulnerability for the demo
set -e

echo "=== Starting Demo ==="

# Clean up any previous demo branch
git checkout main
git pull
git branch -D demo/user-search 2>/dev/null || true
git push origin --delete demo/user-search 2>/dev/null || true

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
git push -u origin demo/user-search
gh pr create --title "Add user search endpoint" \
  --body "Search users by name for the frontend team." \
  --base main --head demo/user-search

echo ""
echo "=== PR created. Switch to Harness UI to watch the review. ==="
