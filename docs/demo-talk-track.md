# Demo Talk Track — 5-10 Minutes

## Opening (30 seconds)

"Thanks for having me. I built this demo to show not just that I can use Harness, but how I'd help a customer solve a real problem: getting AI-powered security into their CI/CD pipeline without sending their code to the cloud. Everything you're about to see runs on local infrastructure — the builds, the AI model, the deployments. Harness is the intelligence layer on top."

## Act 1: The App and Pipeline (2 minutes)

**Show**: The Harness pipeline in the UI — both stages visible.

"Here's a Python FastAPI application deployed to Kubernetes through Harness. The pipeline has two stages:

First, **Build and Test** — it runs an AI code review using Gemma 4, a 26-billion parameter model running on-prem via Ollama. Then pytest, then builds and pushes a Docker image to DockerHub. That build step is a **templatized step** — reusable across any team's pipeline.

Second, **Deploy to Dev** — a canary deployment. Harness deploys one pod first, validates it, then rolls out to full replicas. If anything goes wrong, it rolls back automatically.

The whole thing triggers on a git push — no one has to click 'run.'"

**Show**: The app running in the browser (localhost:8080) — landing page, health check, API docs.

"And here's the deployed app. Health checks, build metadata, auto-generated API docs — all running in Kubernetes."

## Act 2: The AI Security Gate — Live Demo (4 minutes)

**This is the centerpiece. Do this live.**

"Now let me show you what happens when a developer introduces a security vulnerability."

**Step 1**: Open a terminal. Create a branch and add a SQL injection.

```bash
git checkout -b demo/sql-injection
```

Open `app/main.py` and add after the `/api/info` endpoint:

```python
@app.get("/api/search")
def search_users(query: str):
    import sqlite3
    conn = sqlite3.connect("users.db")
    cursor = conn.execute(f"SELECT * FROM users WHERE name LIKE '%{query}%'")
    results = cursor.fetchall()
    conn.close()
    return {"results": results}
```

"Classic SQL injection. An f-string with user input directly in the query. Let's see if the AI catches it."

**Step 2**: Push and open a PR.

```bash
git add app/main.py
git commit -m "Add user search"
git push -u origin demo/sql-injection
gh pr create --title "Add user search" --body "Search users by name" --base main
```

**Step 3**: Switch to Harness UI. Show the pipeline running.

"The webhook fired automatically. Harness is now cloning the code and sending it to our on-prem Gemma 4 model for review."

**Step 4**: Wait ~60 seconds. Click into the AI Code Review step when it fails.

"And there it is — **CRITICAL: SQL Injection, A03:2021**. The AI identified the f-string injection, provided the OWASP classification, and even gave the fix: use parameterized queries. The pipeline is blocked. No tests run. No image builds. No deployment happens."

**Step 5**: Switch to GitHub. Show the PR.

"Back in GitHub — the check failed. And because we have branch protection, the merge button is blocked. This code cannot reach production."

**Step 6**: Pause for impact.

"Think about what just happened. A developer pushed code. An AI model running on the customer's own hardware — not OpenAI, not Anthropic, not any cloud API — reviewed that code in 20 seconds, found a critical security vulnerability, blocked the deployment, and reported the status back to GitHub. No code left the network. Full audit trail in Harness."

**Step 7**: Show the Output tab on the AI Code Review step.

"And look at the Output tab — structured data from the review. Verdict: BLOCKED. Critical count: 1. The findings right there, no log scrolling needed. These output variables can be consumed by downstream steps or external systems."

**Step 8**: Fix the code. Push to the same branch.

Replace the vulnerable search endpoint with the fixed version:

```python
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
```

```bash
git add app/main.py
git commit -m "Fix SQL injection - use parameterized query"
git push
```

**Step 9**: Switch to Harness. Show the pipeline re-running.

"We fixed the injection — parameterized query, explicit columns, proper error handling. The pipeline is re-running automatically."

**Step 10**: Show the AI Code Review step passing. Click Output tab.

"Verdict: PASSED_WITH_WARNINGS. No more critical findings. The Security Gate passes. Tests run. Image builds. Canary deploy to Kubernetes."

**Step 11**: Switch to GitHub. Show checks passing, merge button enabled.

"GitHub checks are green. The merge button is enabled. This code is safe to ship."

*Optional*: Click merge to complete the story.

## Act 3: The Business Value (2 minutes)

"So why does this matter for an enterprise customer?

**First, data sovereignty.** Regulated industries — finance, healthcare, government — can't send proprietary code to third-party AI APIs. With this architecture, the LLM runs on their infrastructure. Harness orchestrates it. Zero data exfiltration risk.

**Second, shift-left security.** This vulnerability was caught before tests even ran. Traditional security scanning happens at the end of the pipeline or in a separate tool. Here it's the first step — and it blocks deployment in real time.

**Third, configurability.** We tested 10 different vulnerability scenarios against this setup."

**Show**: Pull up `docs/ai-code-review-experiments.md` in the browser (GitHub).

"SQL injection, command injection, path traversal, ReDoS, hardcoded secrets — it caught all of them. We also tested prompt engineering to tune severity levels. An organization can define their own security policy in the prompt — 'wildcard CORS is critical for us' — and the AI enforces it.

**Fourth, the platform story.** This isn't a bolted-on tool. It's a pipeline step in Harness, running on the delegate, using the same governance — RBAC, OPA policies, approval gates — that controls everything else. It's not AI instead of your pipeline. It's AI inside your pipeline."

## Closing (30 seconds)

"I built this in two days using Claude Code, the Harness MCP server, and a local Ollama instance. The whole thing is open source in my GitHub repo. I'm happy to dig into any technical detail — the pipeline YAML, the canary strategy, the prompt engineering, the experiment results — wherever you'd like to go."

---

## Prep Checklist

Before the demo:

- [ ] `kubectl port-forward -n harness-demo svc/harness-demo 8080:80` (keep the app accessible)
- [ ] Make sure Docker Desktop K8s is running (`kubectl get nodes`)
- [ ] Make sure Ollama is running on kepler.local (`curl http://kepler.local:11434/api/tags`)
- [ ] Have the Harness UI open: pipeline view
- [ ] Have GitHub open: the repo
- [ ] Have `docs/ai-code-review-experiments.md` open in a browser tab
- [ ] Make sure you're on `main` branch and it's clean (`git status`)
- [ ] Delete any leftover `demo/*` branches from practice runs
- [ ] Have Claude Code open with MCP server connected (for Q&A)

## Likely Technical Questions

**"How does the AI review scale to larger codebases?"**
The current implementation sends all Python files in `app/`. For larger codebases, you'd scope it to changed files only (using `git diff`), or split reviews by module. The Ollama API supports 262K context on Gemma 4.

**"What if the model hallucinates a vulnerability?"**
That's why we only block on CRITICAL findings, not WARNINGs. And the review is visible in the pipeline logs — a developer can see exactly what the AI flagged and override if needed. It's a gate, not a jail.

**"Why not use Harness STO instead?"**
STO is complementary. STO runs traditional SAST/DAST/SCA scanners (Snyk, Checkmarx, etc.). The LLM review catches things those miss — like ReDoS patterns, framework-specific issues (FastAPI query params), and business logic bugs. Best practice is both.

**"How does this compare to GitHub Copilot code review?"**
Copilot sends your code to Microsoft's cloud. This keeps everything on-prem. For regulated industries, that's the deciding factor. Also, the model is swappable — Gemma today, Llama tomorrow, a fine-tuned model next quarter.

**"Can you show me the Harness MCP server?"**
Yes — open Claude Code and ask "what's the status of my latest pipeline run?" or "diagnose the last failed execution." It queries Harness in real time through the MCP protocol.
