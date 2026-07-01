#!/bin/bash
# Fixes the SQL injection vulnerability on the GitLab demo branch
set -e

echo "=== Applying Fix (GitLab) ==="

git checkout demo/user-search

# Remove the vulnerable code (last 9 lines) and add the fix
head -n -9 app/main.py > /tmp/main_fixed.py
mv /tmp/main_fixed.py app/main.py

cat >> app/main.py << 'PYEOF'

@app.get("/api/search")
def search_users(query: str):
    try:
        with sqlite3.connect(settings.DATABASE_PATH) as conn:
            cursor = conn.execute(
                "SELECT id, username, display_name FROM users WHERE username LIKE ?",
                (f"%{query}%",),
            )
            results = [
                {"id": r[0], "username": r[1], "display_name": r[2]}
                for r in cursor.fetchall()
            ]
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"results": results}
PYEOF

git add app/main.py
git commit -m "Fix SQL injection - use parameterized query"
git push gitlab demo/user-search

echo ""
echo "=== Fix pushed to GitLab. Watch the pipeline re-run in Harness. ==="
