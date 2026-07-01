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

critical_lines = [l.strip() for l in review.split("\n") if "**CRITICAL" in l or "* CRITICAL" in l]
warning_lines = [l.strip() for l in review.split("\n") if "**WARNING" in l or "* WARNING" in l]
has_request_changes = "REQUEST CHANGES" in review.upper()

security_criticals = [
    l for l in critical_lines
    if any(kw in l.lower() for kw in SECURITY_KEYWORDS)
]

should_block = len(security_criticals) > 0 and has_request_changes
verdict = "BLOCKED" if should_block else (
    "PASSED_WITH_WARNINGS" if has_request_changes else "APPROVED"
)

crit = '; '.join(
    l.replace("*", "").replace("`", "").strip() for l in critical_lines
) if critical_lines else "None"
warn = '; '.join(
    l.replace("*", "").replace("`", "").strip() for l in warning_lines
) if warning_lines else "None"

if should_block:
    print(f"BLOCKED: {len(security_criticals)} security-critical issue(s) found — fix before deploying")
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
    ("CRITICAL_COUNT", str(len(critical_lines))),
    ("WARNING_COUNT", str(len(warning_lines))),
    ("CRITICAL_FINDINGS", crit),
    ("WARNING_FINDINGS", warn),
]:
    with open(f"/tmp/review/{name}", "w") as f:
        f.write(val)

# Exit code written separately — bash reads it after exporting
with open("/tmp/review/EXIT_CODE", "w") as f:
    f.write("1" if should_block else "0")
