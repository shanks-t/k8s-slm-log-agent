# This a Today I Learned (TIL) section for my project

The goal is to capture things in writing that I learn everyday as I make design decisions, run into gotchas or figure cool concetps to appy in my project. This is tardy, since I've already learned quite a lot -- so I'll have a section for aggregating past learning that I can recall, much of this is in comments in service or other readme. For all new learnings, I'll try to keep them organized by date I discovered them.

## 01-05-26
- The Dependency Lifecycle Pattern is very important to understand and use in FastAPI. Life cycle hooks can be defined by the [async context manager decorator](./workloads/log-analyzer/src/log_analyzer/main.py#L28)
- Config Management for LLM Services: Infra vs Runtime
    **Belongs in Settings Pydantic vars**
    - Infra (Env specific rarely changes, own by Ops):
        - “How do I reach things, and how does the service run?” e.g.
        - llm url
        - timeouts
        - retry limits
    ** Belongs in prompt template**
    - Runtime (Model Behavior)
        - “How should the model behave for this task?” e.g.
        - temperature
        - max tokens
        - top_p
        - model name
        - streaming vs non-stream

## 01-06-26
- ASGI (Asynchronous Server Gateway Interface) models HTTP as a series of events, not a single request-response pair. OpenTelemetry's FastAPI instrumentation creates spans for each ASGI event to provide visibility into the request lifecycle. For streaming responses, the "http.disconnect" span is particularly important - it shows how long the stream was kept open, which is crucial for understanding client behavior and detecting premature disconnects vs. successful completions.