import glob
import json
import sys

import requests

OLLAMA_URL = "http://kepler.local:11434/api/generate"
MODEL = "gemma4:26b-a4b-it-qat"

SECURITY_KEYWORDS = [
    "injection", "sqli", "xss", "csrf", "ssrf", "redirect", "traversal",
    "credential", "secret", "password", "hardcoded", "authentication",
    "authorization", "cors", "exposure", "disclosure", "sensitive",
    "a01:", "a02:", "a03:", "a04:", "a05:", "a06:", "a07:", "a08:", "a09:", "a10:",
]

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
    "Severity guidelines:\n"
    "- CRITICAL: Any injection (SQL, command, SSRF), hardcoded secrets, "
    "authentication/authorization bypass, wildcard CORS with credentials, "
    "unvalidated redirects, path traversal, sensitive data in logs or URLs, "
    "race conditions with shared mutable state, ReDoS patterns.\n"
    "- WARNING: Information disclosure, missing input validation, "
    "inefficient resource management, missing error handling.\n"
    "- INFO: Style issues, minor best practice deviations.\n\n"
    "Provide a concise review with these severity levels.\n"
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

import re

def count_severity(text, severity):
    count = 0
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith(("*", "-")) and re.search(rf'\*\*{severity}', line, re.IGNORECASE):
            count += 1
    return count

critical_count = count_severity(review, "CRITICAL")
warning_count = count_severity(review, "WARNING")
has_request_changes = "REQUEST CHANGES" in review.upper()
has_security_critical = critical_count > 0 and any(
    kw in review.lower() for kw in SECURITY_KEYWORDS
)

should_block = has_security_critical and has_request_changes
verdict = "BLOCKED" if should_block else (
    "PASSED_WITH_WARNINGS" if has_request_changes else "APPROVED"
)

if should_block:
    print(f"BLOCKED: Security-critical issue(s) found — fix before deploying")
elif has_request_changes:
    print("WARNING: AI reviewer requested changes (non-critical) — proceeding with caution")
else:
    print("AI review passed — no issues found")

# Write values to individual files for bash to read
import os
os.makedirs("/tmp/review", exist_ok=True)
for name, val in [
    ("REVIEW_VERDICT", verdict),
    ("REVIEW_MODEL", MODEL),
    ("REVIEW_TOKENS", str(tokens)),
    ("REVIEW_TIME", f"{duration}s"),
    ("REVIEW_FILES", ", ".join(code_files)),
    ("CRITICAL_COUNT", str(critical_count)),
    ("WARNING_COUNT", str(warning_count)),
]:
    with open(f"/tmp/review/{name}", "w") as f:
        f.write(val)
