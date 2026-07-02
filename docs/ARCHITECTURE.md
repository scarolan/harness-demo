# Architecture

## System Overview

```mermaid
graph TB
    subgraph Internet
        HARNESS[Harness SaaS<br/>app.harness.io]
        GITHUB[GitHub<br/>scarolan/harness-demo]
        DOCKERHUB[DockerHub<br/>carolanio/harness-demo]
    end

    subgraph Home Network
        subgraph Docker Desktop Kubernetes
            subgraph harness-delegate-ng
                DELEGATE[demo-delegate pod<br/>Helm chart install<br/>Polls Harness for tasks]
            end
            subgraph harness-ci
                BUILD[Ephemeral Build Pods<br/>AI Review / Tests / Kaniko<br/>Created per pipeline run]
            end
            subgraph harness-demo
                APP1[harness-demo pods x2<br/>Python FastAPI<br/>NodePort 30080]
            end
        end
        OLLAMA[Ollama on kepler<br/>Gemma 4 26B QAT<br/>192.168.1.146:11434]
        GITLAB[GitLab on-prem<br/>gitlab.local]
    end

    GITHUB -->|webhook| HARNESS
    GITLAB -->|webhook| HARNESS
    DELEGATE -->|long-poll HTTPS<br/>outbound only| HARNESS
    HARNESS -->|task instructions| DELEGATE
    DELEGATE -->|spawns| BUILD
    DELEGATE -->|deploys| APP1
    BUILD -->|clone code| GITHUB
    BUILD -->|clone code| GITLAB
    BUILD -->|AI review| OLLAMA
    BUILD -->|push image| DOCKERHUB
```

## Communication Model

The delegate initiates all connections outbound. Harness SaaS never calls in.

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant GH as GitHub
    participant HS as Harness SaaS
    participant DG as Delegate Pod
    participant CI as CI Build Pod
    participant OL as Ollama (kepler)
    participant K8 as K8s (harness-demo)

    Dev->>GH: git push / open PR
    GH->>HS: webhook (push/PR event)
    HS->>HS: match trigger, queue pipeline

    loop Delegate long-poll
        DG->>HS: any tasks for me?
        HS->>DG: run pipeline (clone, review, test, build, deploy)
    end

    DG->>CI: create build pod in harness-ci namespace

    CI->>GH: git clone (via connector)
    CI->>OL: POST /api/generate (code review)
    OL->>CI: JSON findings + verdict

    alt CRITICAL findings
        CI->>HS: step failed (exit 1)
        HS->>GH: status check: failed
    else Clean review
        CI->>CI: run pytest
        CI->>CI: kaniko build
        CI->>CI: push to DockerHub
        CI->>HS: build stage complete
        DG->>K8: canary deploy (1 pod)
        DG->>K8: rolling deploy (all pods)
        HS->>GH: status check: passed
    end
```

## Kubernetes Namespaces

| Namespace | Purpose | Contents |
|-----------|---------|----------|
| `harness-delegate-ng` | Delegate runtime | `demo-delegate` pod + auto-upgrader jobs |
| `harness-ci` | CI build infrastructure | Ephemeral pods per pipeline run (empty between runs) |
| `harness-demo` | Python app deployment | 2 replicas, NodePort 30080 |
| `harness-petclinic` | Java app deployment | 2 replicas, NodePort 30081 |

## The Delegate

The delegate is the bridge between Harness SaaS and your local infrastructure. Key properties:

- **Outbound only** -- it polls `https://app.harness.io`, no inbound ports or firewall holes needed
- **Installed via Helm** -- `harness-delegate-ng` chart, single `helm install` command
- **Auto-upgrades** -- periodic upgrader jobs check for new versions
- **Network access** -- can reach everything on the home network (GitLab, Ollama) plus the internet (GitHub, DockerHub)
- **Authenticated** -- registered to the Harness account with a delegate token

```bash
# How the delegate was installed
helm repo add harness-delegate \
  https://app.harness.io/storage/harness-download/delegate-helm-chart/
helm install demo-delegate harness-delegate/harness-delegate-ng \
  --namespace harness-delegate-ng \
  --set accountId=<ACCOUNT_ID> \
  --set delegateToken=<TOKEN_FROM_UI> \
  --set delegateName=demo-delegate \
  --set managerEndpoint=https://app.harness.io
```

## CI Build Pods

Each pipeline run creates ephemeral containers in the `harness-ci` namespace:

| Step | Container Image | What It Does |
|------|----------------|--------------|
| AI Code Review | `python:3.12-slim` | Sends code to Ollama, parses JSON verdict |
| Security Gate | `alpine` | Reads verdict, blocks on CRITICAL |
| Run Tests | `python:3.12-slim` | `pytest` (Python) or `mvnw test` (Java) |
| Build & Push | Kaniko | Builds Docker image, pushes to DockerHub |

These pods are created at pipeline start and destroyed when it finishes. The `harness-ci` namespace is empty between runs.

## On-Prem AI Review

```mermaid
graph LR
    subgraph CI Pod
        SCRIPT[ai_review.py]
    end
    subgraph Kepler Server
        OLLAMA[Ollama API<br/>:11434]
        GEMMA[Gemma 4 26B QAT<br/>15.6GB VRAM]
    end

    SCRIPT -->|POST /api/generate<br/>source code + schema| OLLAMA
    OLLAMA -->|structured JSON<br/>findings + verdict| SCRIPT
```

- Model runs permanently on `kepler` (192.168.1.146) with keep-alive
- Context window: 16,384 tokens (set via `num_ctx`)
- Structured JSON output via Ollama schema enforcement
- Review time: ~15-25 seconds per run
- Retry logic: up to 3 attempts on JSON parse failure
- No code leaves the network

## Deployment Strategy

```mermaid
graph LR
    A[New Image Built] --> B[Canary Deploy<br/>1 pod with new version]
    B --> C{Healthy?}
    C -->|Yes| D[Canary Delete]
    D --> E[Rolling Deploy<br/>all replicas updated]
    C -->|No| F[Canary Rollback]
    F --> G[Rolling Rollback<br/>previous version restored]
```
