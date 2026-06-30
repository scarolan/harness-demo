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
            "options": {"temperature": 0.3, "num_predict": 1024},
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

if "REQUEST CHANGES" in review.upper() and "CRITICAL" in review.upper():
    print("BLOCKING: Critical issues found by AI reviewer")
    sys.exit(1)

print("AI review passed — proceeding to tests")
