import glob
import json
import os
import sys

import requests

OLLAMA_URL = "http://kepler.local:11434/api/generate"
MODEL = "gemma4:26b-a4b-it-qat"

SECURITY_KEYWORDS = [
    "injection", "sqli", "xss", "csrf", "ssrf", "redirect", "traversal",
    "credential", "secret", "password", "hardcoded", "authentication",
    "authorization", "cors", "exposure", "disclosure", "sensitive",
]

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["CRITICAL", "WARNING", "INFO"]},
                    "category": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "file": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
                "required": ["severity", "category", "title", "description"],
            },
        },
        "verdict": {"type": "string", "enum": ["APPROVE", "REQUEST CHANGES"]},
    },
    "required": ["findings", "verdict"],
}

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
    "Return your review as JSON matching this schema.\n"
    "Set verdict to APPROVE if no CRITICAL or WARNING issues, "
    "otherwise REQUEST CHANGES.\n\n"
    + code
)

print(f"Reviewing {len(code_files)} files: {', '.join(code_files)}")
print(f"Model: {MODEL}")
print()
print("Sending code to AI model for security review...")
print("(This typically takes 15-25 seconds)")
print()

try:
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "format": REVIEW_SCHEMA,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": -1},
        },
        timeout=120,
    )
    result = resp.json()
except Exception as e:
    print(f"ERROR: Could not reach Ollama at {OLLAMA_URL}: {e}")
    print("AI review is required — cannot proceed without it.")
    sys.exit(1)

raw = result.get("response", "{}")
tokens = result.get("eval_count", 0)
duration = round(result.get("eval_duration", 0) / 1e9, 1)

try:
    review = json.loads(raw)
except json.JSONDecodeError:
    print(f"ERROR: Model returned invalid JSON — review failed")
    print(raw[:500])
    sys.exit(1)

# Pretty-print findings for the log tab
findings = review.get("findings", [])
verdict = review.get("verdict", "APPROVE")

for f in findings:
    severity = f.get("severity", "?")
    title = f.get("title", "?")
    category = f.get("category", "?")
    desc = f.get("description", "")
    rec = f.get("recommendation", "")
    file = f.get("file", "")

    icon = {"CRITICAL": "!!!", "WARNING": " ! ", "INFO": " i "}.get(severity, " ? ")
    print(f"[{icon}] {severity}: {title}")
    print(f"     Category: {category}")
    if file:
        print(f"     File: {file}")
    print(f"     {desc}")
    if rec:
        print(f"     Fix: {rec}")
    print()

critical_count = sum(1 for f in findings if f.get("severity") == "CRITICAL")
warning_count = sum(1 for f in findings if f.get("severity") == "WARNING")
info_count = sum(1 for f in findings if f.get("severity") == "INFO")

security_criticals = [
    f for f in findings
    if f.get("severity") == "CRITICAL"
    and any(kw in json.dumps(f).lower() for kw in SECURITY_KEYWORDS)
]

should_block = len(security_criticals) > 0 and verdict == "REQUEST CHANGES"
final_verdict = "BLOCKED" if should_block else (
    "PASSED_WITH_WARNINGS" if verdict == "REQUEST CHANGES" else "APPROVED"
)

print("=" * 60)
print(f"VERDICT: {final_verdict}")
print(f"Findings: {critical_count} critical, {warning_count} warning, {info_count} info")
print(f"[Tokens: {tokens} | Time: {duration}s | Model: {MODEL}]")
print("=" * 60)

if should_block:
    print(f"BLOCKED: {len(security_criticals)} security-critical issue(s) found")
elif verdict == "REQUEST CHANGES":
    print("WARNING: Non-critical issues found — proceeding with caution")
else:
    print("AI review passed — no issues found")

# Write values to individual files for bash to read
critical_titles = "; ".join(f.get("title", "") for f in findings if f.get("severity") == "CRITICAL")
warning_titles = "; ".join(f.get("title", "") for f in findings if f.get("severity") == "WARNING")

os.makedirs("/tmp/review", exist_ok=True)
for name, val in [
    ("REVIEW_VERDICT", final_verdict),
    ("REVIEW_MODEL", MODEL),
    ("REVIEW_TOKENS", str(tokens)),
    ("REVIEW_TIME", f"{duration}s"),
    ("REVIEW_FILES", ", ".join(code_files)),
    ("CRITICAL_COUNT", str(critical_count)),
    ("WARNING_COUNT", str(warning_count)),
    ("CRITICAL_FINDINGS", critical_titles or "None"),
    ("WARNING_FINDINGS", warning_titles or "None"),
]:
    with open(f"/tmp/review/{name}", "w") as f:
        f.write(val)
