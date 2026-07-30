<p align="center">
  <img src="docs/captain_canary.png" alt="Captain Canary" width="200">
</p>

<h1 align="center">Harness Demo App</h1>

<p align="center">
  <strong>AI-Powered CI/CD with On-Prem Code Review</strong><br>
  A complete Harness CI/CD pipeline with Gemma 4 AI security gate, canary deployments, and zero data exfiltration.
</p>

<p align="center">
  <img src="docs/harness_logo_white.avif" alt="Harness" height="30">
</p>

---

## What This Is

A FastAPI application deployed to Kubernetes via Harness CI/CD, with an AI-powered code review gate using Google Gemma 4 running on-prem via Ollama. Built as a technical exercise for a Harness Solutions Engineer interview.

**The key insight**: Enterprise customers can get AI-powered security scanning in their CI/CD pipeline without sending a single line of code to the cloud.

## Architecture

```
Developer pushes code
  --> GitHub webhook
  --> Harness CI/CD Pipeline
        |
        +--> GitHub Status: pending
        |
        +--> AI Code Review (Gemma 4 26B via Ollama - on-prem)
        |      Returns structured JSON: findings, severity, verdict
        |      CRITICAL security issues --> pipeline BLOCKED
        |
        +--> Security Gate
        |      Reads AI verdict, enforces pass/fail
        |
        +--> Run Tests (pytest)
        |
        +--> Build & Push Docker Image (templatized step)
        |
        +--> GitHub Status: success / failure (always runs)
        |      Reports the AI verdict back to the PR
        |
        +--> Deploy stage (main branch only -- PRs validate, they don't deploy)
               |
               +--> Canary Deploy (1 pod)
               +--> Canary Delete
               +--> Rolling Deploy (full rollout)
  --> App live on Kubernetes
```

## Components

| Component | Technology | Where it runs |
|-----------|-----------|---------------|
| Application | Python FastAPI | Kubernetes pod |
| CI/CD Pipeline | Harness | SaaS control plane |
| Build Infrastructure | Harness Delegate | Kubernetes (self-managed) |
| AI Code Review | Gemma 4 26B QAT | On-prem via Ollama |
| Container Registry | DockerHub | Cloud |
| Source Control | GitHub | Cloud |
| Deployment Strategy | Canary + Rolling | Kubernetes |

## Features

- **AI Security Gate**: Gemma 4 reviews every PR for OWASP Top 10 vulnerabilities. SQL injection, command injection, path traversal, hardcoded secrets, ReDoS -- all caught and blocked.
- **Structured JSON Output**: The AI returns structured findings (not markdown), parsed reliably every time. Results appear in the Harness Output tab.
- **Canary Deployments**: New versions deploy to a single canary pod first, then roll out to full replicas with automatic rollback on failure.
- **Pipeline Templates**: The Docker build step is templatized for reuse across teams.
- **Git Triggers**: Pipeline runs automatically on push to main and on PR open/update.
- **PR Status Reporting**: The pipeline posts `harness/ai-code-review` back to the commit -- pending on start, then pass/fail carrying the actual finding text and a link to the Harness execution. It reports even when the gate blocks the build.
- **Branch Protection**: GitHub requires the AI review check to pass before PRs can be merged.
- **Harness MCP Server**: AI-native platform interaction via Model Context Protocol.

## AI Code Review Experiments

We tested 10 vulnerability scenarios against the AI reviewer. Results:

| # | Scenario | Detected? | Severity |
|---|----------|-----------|----------|
| 1 | Hardcoded secrets | Yes | CRITICAL |
| 2 | Command injection | Yes | CRITICAL |
| 3 | Open redirect | Yes | CRITICAL |
| 4 | Debug endpoint (env vars) | Yes | CRITICAL |
| 5 | Path traversal | Yes | CRITICAL |
| 6 | Logging passwords | Yes | CRITICAL x2 |
| 7 | Insecure CORS | Yes | WARNING (CRITICAL with prescriptive prompt) |
| 8 | ReDoS | Yes | CRITICAL |
| 9 | Clean feature | Passed correctly | No false positive |
| 10 | Race condition | Partial | WARNING |

**7/10 blocked, 0 false positives, 0 false negatives on security-critical issues.**

Full analysis with model comparisons (26B QAT vs 31B) and prompt engineering results: [docs/ai-code-review-experiments.md](docs/ai-code-review-experiments.md)

## Running the Demo

### Prerequisites

- Rancher Desktop with Kubernetes enabled
- Ollama running on `localhost:11434` with the `gemma4:26b` model (the pipeline reaches it
  at `host.docker.internal:11434`, since `localhost` inside a CI pod is the pod itself)
- Harness account with delegate installed
- GitHub and DockerHub accounts

### Demo Scripts

```bash
# Inject a SQL vulnerability, open a PR -- watch Gemma block it
./scripts/demo-start.sh

# Fix the vulnerability, push -- watch Gemma approve it
./scripts/demo-fix.sh

# Clean up for next demo run
./scripts/demo-reset.sh
```

### Local Development

Instead of running the Python app directly, we now deploy everything to Kubernetes locally.

```bash
# Build and deploy the app to your local Kubernetes cluster
./scripts/deploy-local.sh

# Run tests
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -v tests/
```

## Project Structure

```
harness-demo/
  app/
    main.py              # FastAPI application
    config.py            # Environment-based configuration
    static/              # Static assets (Harness logo)
    templates/           # Jinja2 HTML templates
  tests/
    test_main.py         # 9 pytest tests
  scripts/
    ai_review.py         # Gemma 4 AI code review (JSON mode)
    github_status.py     # Posts the AI verdict as a GitHub commit status
    demo-start.sh        # Inject vulnerability for demo
    demo-fix.sh          # Fix vulnerability for demo
    demo-reset.sh        # Reset demo state (restores dev to main's image)
    deploy-local.sh      # Build and deploy straight to local Kubernetes
    gitlab-demo-*.sh     # Same three-act demo against on-prem GitLab
    check-pipeline-drift.sh  # Diffs .harness/ copies against the live Harness entities
  k8s/
    deployment.yaml      # K8s deployment with probes
    service.yaml         # NodePort service
    namespace.yaml       # Dedicated namespace
  docs/
    demo-talk-track.md   # 5-10 minute demo script
    ARCHITECTURE.md      # Diagrams: delegate model, namespaces, deploy strategy
    ai-code-review-experiments.md  # 10 experiment results
  .harness/
    pipelines/           # Local copies -- the live entities are INLINE (see note below)
    templates/           # Templatized Docker build & push step
    triggers/            # Push-to-main and pull-request webhook triggers
    manifests/           # K8s manifests + values.yaml the Deploy stage renders
  Dockerfile             # Single-stage Python build
  requirements.txt       # Python dependencies
```

## A Note on `.harness/`

The pipeline, template, and triggers are all `storeType: INLINE` -- Harness holds the
authoritative YAML in its own database, and the files under `.harness/` are
hand-maintained copies. **Committing a change to those files does not change what runs.**
Apply the change in the Harness UI or via the API; the file is documentation.

Drift is silent in both directions, so there's a check for it:

```bash
./scripts/check-pipeline-drift.sh          # exits 1 and shows a diff if anything drifted
./scripts/check-pipeline-drift.sh --pull   # overwrite local copies from live, then commit
```

Converting these to Remote (git-synced) would make the repo authoritative and remove the
duplication. That's a deliberate change -- it also means a PR could modify the pipeline
that gates it -- so it hasn't been done.

## Issues & Findings

During the build, we documented 11 platform issues with root causes and fixes. Highlights:

- Kaniko multi-stage Dockerfile bug (`device or resource busy`)
- Harness Cloud requires credit card with no self-service upgrade path
- Output variables lost when step exits non-zero (appended capture lines)
- UI 404s with `/admin/` vs `/all/` URL routing
- Harness posts its own commit status only when a stage *fails*, so passing commits
  looked statusless -- fixed by publishing `harness/ai-code-review` explicitly
- `localhost` inside a CI pod is the pod, not the host, so the AI review couldn't
  reach Ollama -- fixed with `host.docker.internal` plus host-gateway fallbacks

---

<p align="center">
  Built with Claude Code, Harness CI/CD, and Gemma 4 via Ollama<br>
  <em>No code left the network.</em>
</p>
