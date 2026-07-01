#!/bin/bash
# Fixes the SQL injection — run this after showing the blocked PR
set -e

echo "=== Applying Fix ==="

git checkout demo/user-search

# Replace the vulnerable endpoint with the fixed version
python3 -c "
code = open('app/main.py').read()
vuln = '''
@app.get(\"/api/search\")
def search_users(query: str):
    import sqlite3
    conn = sqlite3.connect(\"users.db\")
    cursor = conn.execute(f\"SELECT * FROM users WHERE name LIKE '%{query}%'\")
    results = cursor.fetchall()
    conn.close()
    return {\"results\": results}
'''
fixed = '''
@app.get(\"/api/search\")
def search_users(query: str):
    try:
        with sqlite3.connect(settings.DATABASE_PATH) as conn:
            cursor = conn.execute(
                \"SELECT id, username, display_name FROM users WHERE username LIKE ?\",
                (f\"%{query}%\",),
            )
            results = [
                {\"id\": r[0], \"username\": r[1], \"display_name\": r[2]}
                for r in cursor.fetchall()
            ]
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail=\"database unavailable\")
    return {\"results\": results}
'''
open('app/main.py', 'w').write(code.replace(vuln.strip(), fixed.strip()))
"

git add app/main.py
git commit -m "Fix SQL injection - use parameterized query"
git push

echo ""
echo "=== Fix pushed. Watch the pipeline re-run in Harness. ==="
