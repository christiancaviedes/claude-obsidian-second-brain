# Claude Obsidian Second Brain

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/christiancaviedes/claude-obsidian-second-brain/actions/workflows/ci.yml/badge.svg)](https://github.com/christiancaviedes/claude-obsidian-second-brain/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-27%25-yellowgreen.svg)](.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/christiancaviedes/claude-obsidian-second-brain.svg?style=social)](https://github.com/christiancaviedes/claude-obsidian-second-brain)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/christiancaviedes/claude-obsidian-second-brain/pulls)

## Transform your Claude conversation history into a living, searchable second brain.

You have months or years of conversations in Claude — architectural decisions, research sessions, debugging breakthroughs, strategy discussions. It's all locked in a linear export file, unsearchable, unlinked, and forgotten.

This 10-agent pipeline parses your Claude exports, extracts knowledge, and generates a fully organized Obsidian vault: bidirectional wikilinks, Maps of Content, topic clusters, and a knowledge graph that shows how your thinking connects across time.

---

## Features

- **10-agent coordinated pipeline** — focused stages parse, clean, tag, extract, graph, link, generate MOCs, format, and index, with orchestration and checkpoints
- **Auto-generated wikilinks** — semantic cross-linking across conversations with configurable similarity threshold
- **Maps of Content (MOCs)** — topic overview pages auto-generated for every major cluster
- **Rich frontmatter** — every note tagged with date, topics, key decisions, action items, and source metadata
- **Knowledge graph ready** — open in Obsidian and instantly see your ideas connected visually
- **Code snippet extraction** — significant code blocks saved as separate linked notes
- **Action item aggregation** — all TODOs and decisions surfaced to a single Open Tasks note
- **Incremental processing** — run again after new exports, only new conversations processed
- **Both export formats** — handles Claude's JSON and HTML export formats

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/christiancaviedes/claude-obsidian-second-brain.git
cd claude-obsidian-second-brain
python3.11 -m venv venv && source venv/bin/activate
python -m pip install -e .

# 2. Configure
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# 3. Export your Claude conversations
# claude.ai → Settings → Account → Export Data → Download

# 4. Run the pipeline
claude-obsidian validate examples/sample-export.json
claude-obsidian run /path/to/claude-export.json --output ./my-second-brain

# 5. Open in Obsidian
# File > Open Vault > select "my-second-brain" folder
```

---

## Verified CLI

The repository ships a synthetic export so its public claims can be reproduced without
using private conversation data:

```bash
claude-obsidian validate examples/sample-export.json
python -m pytest
```

CI runs those checks on Python 3.10, 3.11, and 3.12. Runtime and output quality depend on
export size, model selection, network latency, and configuration; this project does not
present offline validation speed as a model-quality claim.

**See it before running it:** browse the fully synthetic
[sample vault](examples/sample-vault), read the
[architecture decision record](docs/architecture/ADR-001-pipeline-boundaries-and-reliability.md),
or reproduce the [benchmark](benchmarks/README.md).

**Sample generated note:**

```markdown
---
title: "Building a Redis Session Store"
date: 2024-03-12
topics: [redis, authentication, backend, architecture]
key_decisions:
  - Chose Redis over database sessions for horizontal scaling
  - 24h TTL with refresh-on-activity
action_items:
  - Add Redis cluster config for production
source: claude-export.json
---

# Building a Redis Session Store

## Summary
Discussion of implementing a Redis-backed session store for the auth service,
comparing approaches and settling on a TTL-based strategy.

## Key Points
- [[JWT Refresh Token Strategy]] connects here — refresh tokens stored in Redis
- [[Auth Service Architecture]] — parent context for this decision

## Decisions Made
1. Redis over PostgreSQL for session storage: horizontal scaling requirements
2. 24-hour TTL with activity refresh

## Action Items
- [ ] Add Redis cluster config for production deployment

## Related
- [[Authentication Flow Redesign]]
- [[Horizontal Scaling Strategy]]
- [[Redis Performance Benchmarks]]
```

---

## Vault Structure

```
my-second-brain/
├── 000 Index/
│   ├── README.md              # Vault welcome and navigation
│   ├── Topics MOC.md          # Master map of all topics
│   ├── Timeline.md            # Chronological conversation list
│   └── Statistics.md          # Knowledge metrics
│
├── Topics/
│   ├── Coding/
│   │   ├── Coding MOC.md
│   │   ├── Python/
│   │   └── APIs/
│   ├── Strategy/
│   │   └── Strategy MOC.md
│   └── Learning/
│       └── Learning MOC.md
│
├── Conversations/
│   ├── 2024-01-15 Building a REST API.md
│   ├── 2024-02-03 Startup Pricing Strategy.md
│   └── ...
│
├── Action Items/
│   └── Open Tasks.md          # All action items aggregated
│
└── Code Snippets/
    ├── Python/
    └── JavaScript/
```

---

## How It Works

```
Claude Export (JSON/HTML)
         │
         ▼
┌─────────────────────────────────────────────┐
│              INGESTION LAYER                │
│  01 Parser → 02 Cleaner → 03 Tagger         │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│              ANALYSIS LAYER                 │
│  04 Extractor → 05 Graph → 06 Linker        │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│             GENERATION LAYER                │
│  07 MOC Gen → 08 Formatter → 09 Indexer     │
│                        → 10 Orchestrator    │
└─────────────────────────────────────────────┘
         │
         ▼
   Obsidian Vault
```

| Agent | Purpose |
|-------|---------|
| **01 Parser** | Ingests JSON/HTML exports, extracts conversations and metadata |
| **02 Cleaner** | Normalizes text, removes duplicates, fixes encoding |
| **03 Tagger** | Uses Claude to extract topics, categories, semantic tags |
| **04 Extractor** | Identifies key decisions, insights, action items, and code blocks |
| **05 Graph Builder** | Builds relationships and knowledge communities |
| **06 Linker** | Creates bidirectional wikilinks from graph relationships |
| **07 MOC Generator** | Creates Maps of Content per category and topic |
| **08 Formatter** | Writes markdown notes and MOCs with frontmatter |
| **09 Indexer** | Builds timeline, topic, cluster, and statistics pages |
| **10 Orchestrator** | Coordinates stages, retries, checkpoints, and summaries |

---

## Configuration

Edit `config/settings.yaml`:

```yaml
anthropic:
  api_key: ${ANTHROPIC_API_KEY}
  model: claude-sonnet-4-20250514

pipeline:
  parallel_agents: 4
  batch_size: 50
  skip_short: true
  min_exchanges: 3

vault:
  index_folder: "000 Index"
  topics_folder: "Topics"
  conversations_folder: "Conversations"

analysis:
  extract_code_blocks: true
  extract_action_items: true
  link_threshold: 0.7

moc:
  min_notes: 3
  max_depth: 2
```

---

## Performance

The versioned offline benchmark validates the bundled export 100 times without an API:

| Path | Runs | Median | p95 | API calls | API cost |
|---|---:|---:|---:|---:|---:|
| Export validation | 100 | 0.118 ms | 0.129 ms | 0 | $0 |

These August 8, 2026 figures were produced on Python 3.11 and are stored in
[`benchmarks/results/latest.json`](benchmarks/results/latest.json). End-to-end runtime
and output quality depend on export size, model selection, network latency, and
configuration; no unsupported quality or live-API cost claim is made.

## Engineering Evidence

- **Integration:** CI exercises all nine stages with remote AI behavior mocked.
- **Reliability:** stage retries, critical-stage stopping, checkpoints, and resume.
- **Privacy:** deterministic stages stay local; model-bound data flow is documented.
- **Quality gate:** branch coverage is collected on Python 3.10–3.12 and cannot fall
  below the current 20% repository baseline.
- **Architecture:** [ADR-001](docs/architecture/ADR-001-pipeline-boundaries-and-reliability.md)
  records boundaries, concurrency, recovery, privacy, model choice, cost controls, and
  rejected alternatives.

---

## Exporting Your Claude Conversations

1. Go to [claude.ai](https://claude.ai)
2. **Settings** → **Account** → **Export Data**
3. Download the JSON or HTML export file
4. Pass it to `claude-obsidian run`

---

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
ruff check .
mypy agents main.py
```

---

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md). Great areas to contribute:
- Support for ChatGPT / other AI assistant exports
- Custom tagging taxonomies
- Obsidian plugin for incremental imports
- Web UI for configuration
- Advanced graph analysis

---

## License

MIT © 2026 [Christian Caviedes](https://github.com/christiancaviedes)

Built with the [Anthropic API](https://www.anthropic.com/) — designed for [Obsidian](https://obsidian.md/)
