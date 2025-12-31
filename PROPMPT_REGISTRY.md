# Prompt for Agent: Build a Prompt Registry + Intent-Based Prompt Router for My FastAPI + Llama.cpp Homelab Stack

## Context (what exists today)
- Homelab Kubernetes cluster.
- A **FastAPI** service that:
  - queries Loki logs
  - calls a **Llama.cpp** model server
  - returns: (a) summary of what happened, (b) suggested action steps
- Observability already in place:
  - **OpenTelemetry tracing** from FastAPI
  - **Tempo** for trace ingest/storage
  - **Loki** for structured logs
  - **Prometheus** metrics

## Goal
Implement two patterns commonly used by strong LLM engineering teams (scaled down to homelab reality):
1. **Prompt Registry**: structured, versioned prompts (templates + metadata) with stable IDs/hashes.
2. **Intent-Based Routing**: given a request + context, choose which prompt (and version) to run.

This must integrate cleanly with:
- existing FastAPI service
- existing OTel tracing → Tempo
- Kubernetes deployment model (ConfigMaps/Env/Volumes/etc.)
- GitOps workflow (Flux) if possible

---

## Part A — Conceptual grounding: OTel observability vs “LLM observability” platforms
### What to explain/validate
- Compare my current OTel/Tempo/Loki/Prom stack with LLM-specific platforms (e.g., **Opik**, Langfuse).
- Are these “the same thing”?
  - Similar at the *telemetry transport layer*: both can use **OpenTelemetry spans + attributes**.
  - Different at the *LLM product layer*: prompt/version tracking, LLM-specific UIs, evaluation datasets, human feedback, model/prompt comparisons, cost/token breakdowns, guardrails, etc.
- Confirm whether:
  - **Opik supports OpenTelemetry ingestion** (and how).
  - **Langfuse supports OpenTelemetry ingestion** (and how).
  - Mention GenAI semantic conventions (OTel attributes for LLM calls) and how LLM tools map them.

Deliverable: a short explanation that clarifies:
- what I can get “for free” by staying pure OTel
- what I *don’t* get without an LLM-focused backend/UI
- why it may still be worth staying OTel-first in a homelab

---

## Part B — Prompt template attribute: what it should mean (trace semantics)
### What I want
When a request flows through FastAPI, the trace should include attributes that let me answer:
- Which prompt template was used?
- Which version?
- Which variables were injected?
- What was the model config (temperature, top_p, max_tokens, stop)?
- How many input/output tokens (or an estimate)?
- Which “intent route” was chosen and why?

### Define a clean approach
Implement “prompt template” observability as **IDs + hashes**, not raw full text by default:
- `llm.prompt.id`: stable logical name (e.g., `log_triage.k8s.v1`)
- `llm.prompt.version`: semver or monotonic build (e.g., `1.3.0`)
- `llm.prompt.template_sha256`: hash of the *canonical template* string
- `llm.prompt.vars_sha256`: hash of rendered variables (optional)
- `llm.prompt.render_sha256`: hash of fully-rendered prompt (optional)
- `llm.prompt.render_preview`: OPTIONAL short preview (first N chars) only if safe
- `llm.intent`: e.g. `k8s_log_triage`, `summarize`, `recommend_actions`
- `llm.route.reason`: short reason string (rule match / classifier label)

Important: avoid putting full prompts in traces by default (privacy + noise). Prefer hashes + small previews.

Deliverable: propose the attribute scheme + what spans exist:
- parent span: request handler `/v1/analyze`
- child span: `prompt.render`
- child span: `llm.inference` (the actual call to llama.cpp)

---

## Part C — Prompt Registry: how to store + version prompts (homelab-appropriate)
### Requirements
- Prompts are text templates + metadata.
- They must be:
  - versioned
  - reviewable in Git
  - selectable by ID/version at runtime
- Registry should support:
  - list prompts
  - fetch prompt by ID/version
  - render prompt with variables
  - compute hashes
  - optionally validate schema (required variables)

### Recommended file layout (example)
 - Need to determine proper structure for fastapi service

### Versioning strategy
Pick one (and justify):
1. **SemVer per prompt**: `1.0.0`, `1.1.0`…
2. **Git SHA as version**: version = short commit hash
3. **Hybrid**: semver in meta + also record git SHA at runtime

Hashing rules:
- canonicalize template text (normalize line endings, trim trailing whitespace)
- compute SHA256
- store in index for fast lookup and trace attribution

Deliverable: a concrete, minimal registry design that can run inside the FastAPI container.

---

## Part D — How prompts get into the container (Kubernetes options + tradeoffs)
I want you to recommend **one default** approach, plus alternatives.

### Option 1: bake prompts into the container image
How:
- `COPY prompts/ /app/prompts/`
Pros:
- immutable, reproducible
- easy rollback by deploying previous image tag
- simplest runtime (no mounts)
Cons:
- changing prompts requires image rebuild/redeploy
- less flexible for rapid iteration

### Option 2: ConfigMap mount (prompts as files)
How:
- create ConfigMap from `prompts/` files
- mount into container at `/app/prompts`
Pros:
- fast iteration without rebuilding image
- GitOps-friendly (Flux applies ConfigMap)
Cons:
- ConfigMaps have size limits; many prompts can get annoying
- updates roll pods (good) but need discipline
- still “static” unless you add an API to mutate it (usually not desired)

### Option 3: initContainer pulls prompts from Git at startup
How:
- initContainer clones repo (read-only deploy key)
- writes prompts into an `emptyDir` volume mounted by app container
Pros:
- decouples prompts from app image
- easy to pin to a git ref/tag
Cons:
- more moving parts, auth, cold start time
- git availability required

### Option 4: PVC-backed prompt store
How:
- store prompts on a volume
Pros:
- persistent
Cons:
- anti-pattern for versioned config unless you build a whole release process

### Passing “which prompt version to use”
Decide whether prompt selection is controlled by:
- env vars: `DEFAULT_PROMPT_SET=prod`, `PROMPT_VERSION=...`
- ConfigMap values
- request-time param (only for dev)
- router logic (preferred)

Deliverable:
- pick the best default for my homelab
- show the tradeoffs crisply
- recommend how to make “dev vs prod prompts” ergonomic


## Part F — Intent-based routing design (simple but principled)
### Router requirements
- input: request payload + derived features
  - namespace, container, detected error class, log volume, severity, keywords
- output:
  - `intent` (string)
  - `prompt_id`
  - `prompt_version`
  - optional: model parameters policy (temp/max_tokens)
- should be testable deterministically

### Start simple (rule-based), then allow growth
- Phase 1: rules
  - e.g., if `namespace == kube-system` and `detected_level in {error,warn}` → `k8s_core_triage`
- Phase 2: lightweight classifier (optional)
  - even a tiny model or embedding similarity to intent descriptions
  - but keep rule fallbacks

Deliverable:
- propose router interface + how to unit test it
- add trace attributes for routing decision


## Part H — Concrete implementation tasks for the agent
Produce:
1. A minimal **PromptRegistry** module for FastAPI:
   - loads prompts from `/app/prompts`
   - builds index with hashes
   - `get(prompt_id, version)`
   - `render(prompt_id, version, vars)`
2. A minimal **Router** module:
   - rule-based routing function returning intent + prompt selection
   - deterministic + unit tests
3. FastAPI integration:
   - request handler uses router → registry → llama.cpp client
   - emits OTel spans with the attributes defined above
4. Kubernetes deployment guidance:
   - recommend one approach (image-baked prompts OR ConfigMap mount)
   - show how to wire it in via manifests/Helm/Kustomize (high-level is fine)
5. Dev/prod plan:
   - namespaces + overlays + promotion workflow

Success criteria:
- I can answer “which prompt caused this output?” from Tempo traces.
- I can iterate safely in dev and promote to prod via GitOps.
- I can compare prompt versions by hash + trace metadata, even without an LLM-specific platform.

---

## Notes / constraints
- Prefer free/open-source tools.
- Keep it “homelab simple,” but conceptually aligned with excellent practice.
- Avoid heavy dependencies unless they buy real leverage.
- Assume my model server is llama.cpp behind an HTTP API.

---

## (Optional) Stretch goals
- Add evaluation hooks:
  - store request/response pairs and score them (even manually)
  - basic regression tests for prompts (golden inputs)
- Add a “prompt release gate”:
  - dev prompt must pass a small test suite before promotion