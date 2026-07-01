import glob
import json
import sys

import requests

OLLAMA_URL = "http://kepler.local:11434/api/generate"
MODEL = "gemma4:26b-a4b-it-qat"

print("=" * 60)
print("AI CODE REVIEW — Gemma 4 26B (on-prem via Ollama)")
print("=" * 60)
print()

code_files = sorted(glob.glob("app/**/*.py", recursive=True))
code = ""
for f in code_files:
    with open(f) as fh:
        code += f"\n### {f}\n{fh.read()}\n"

prompt = (
    "You are a senior code reviewer. Review this Python application for:\n"
    "1. Security vulnerabilities (OWASP Top 10)\n"
    "2. Code quality issues\n"
    "3. Performance concerns\n"
    "4. Best practice violations\n\n"
    "Provide a concise review with severity levels (CRITICAL/WARNING/INFO).\n"
    "End with a one-line VERDICT: APPROVE or REQUEST CHANGES.\n\n"
    + code
)

print(f"Reviewing {len(code_files)} files: {', '.join(code_files)}")
print(f"Model: {MODEL}")
print()

try:
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": -1},
        },
        timeout=120,
    )
    result = resp.json()
except Exception as e:
    print(f"WARNING: Could not reach Ollama at {OLLAMA_URL}: {e}")
    print("Skipping AI review — proceeding to tests")
    sys.exit(0)

review = result.get("response", "No response")
tokens = result.get("eval_count", 0)
duration = round(result.get("eval_duration", 0) / 1e9, 1)

print(review)
print()
print(f"[Tokens: {tokens} | Time: {duration}s | Model: {MODEL}]")
print("=" * 60)

has_critical = "**CRITICAL" in review or "* CRITICAL" in review
has_request_changes = "REQUEST CHANGES" in review.upper()

# Write output variables to a file for the shell wrapper to export
verdict = "BLOCKED" if (has_critical and has_request_changes) else (
    "PASSED_WITH_WARNINGS" if has_request_changes else "APPROVED"
)
critical_lines = [l.strip() for l in review.split("\n") if "**CRITICAL" in l or "* CRITICAL" in l]
warning_lines = [l.strip() for l in review.split("\n") if "**WARNING" in l or "* WARNING" in l]

with open("/tmp/review_outputs.env", "w") as f:
    f.write(f"REVIEW_VERDICT={verdict}\n")
    f.write(f"REVIEW_MODEL={MODEL}\n")
    f.write(f"REVIEW_TOKENS={tokens}\n")
    f.write(f"REVIEW_TIME={duration}s\n")
    f.write(f"REVIEW_FILES={', '.join(code_files)}\n")
    f.write(f"CRITICAL_COUNT={len(critical_lines)}\n")
    f.write(f"WARNING_COUNT={len(warning_lines)}\n")
    f.write(f"CRITICAL_FINDINGS={' | '.join(critical_lines) if critical_lines else 'None'}\n")
    f.write(f"WARNING_FINDINGS={' | '.join(warning_lines) if warning_lines else 'None'}\n")

if has_critical and has_request_changes:
    print("BLOCKED: Critical issues found — fix before deploying")
    with open("/tmp/review_exit_code", "w") as f:
        f.write("1")
else:
    if has_request_changes:
        print("WARNING: AI reviewer requested changes (non-critical) — proceeding with caution")
    else:
        print("AI review passed — no issues found")
