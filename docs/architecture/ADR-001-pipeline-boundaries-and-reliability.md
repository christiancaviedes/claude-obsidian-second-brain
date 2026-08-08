# ADR-001: Pipeline Boundaries and Reliability Controls

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

Claude exports may contain years of private conversation data. Processing combines
deterministic transformations with slower, metered model calls and file generation.
A single opaque job would be hard to retry, audit, or price.

## Decision

Use nine single-purpose stages coordinated by a tenth orchestrator:

`parse → clean → tag → extract → graph → link → MOC → format → index`

- **Boundaries:** stages exchange typed records or explicit graph/output objects.
- **Concurrency:** only independent, API-heavy records may run concurrently; ordered
  filesystem stages remain serialized. Concurrency is bounded by configuration.
- **Checkpointing:** a successful stage writes a checkpoint. Resume starts at the
  first unfinished stage; a fully successful run deletes the checkpoint.
- **Failure recovery:** each stage retries with increasing delay. Parse and clean are
  critical and stop the run; later failures are reported rather than hidden.
- **Privacy:** exports stay local except for text sent to the configured Anthropic
  model during AI stages. Logs must never include API keys or full source exports.
- **Model choice:** the model is configurable. A balanced default favors structured
  extraction quality; deterministic stages never require a model.
- **Cost controls:** bounded concurrency, batch sizing, incremental processing, and
  checkpoints prevent accidental duplicate model work. Dry-run validation costs $0.

## Alternatives rejected

1. **One large prompt:** simpler, but difficult to resume, test, or constrain.
2. **Fully parallel execution:** faster in theory, but violates stage dependencies and
   makes writes nondeterministic.
3. **Cloud-hosted ingestion by default:** easier onboarding, but creates unnecessary
   custody of sensitive exports.
4. **Hard-coded model:** predictable demos, but prevents cost/quality tradeoffs.

## Consequences

The pipeline has more interfaces and test fixtures, but each stage can be replaced,
benchmarked, and recovered independently. CI includes an end-to-end orchestration test
with all remote AI behavior mocked, proving control flow without external cost or data.
