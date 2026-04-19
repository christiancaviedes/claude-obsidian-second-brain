# Claude Obsidian Second Brain

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/christiancaviedes/claude-obsidian-second-brain.svg?style=social)](https://github.com/christiancaviedes/claude-obsidian-second-brain)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/christiancaviedes/claude-obsidian-second-brain/pulls)

## Transform your Claude conversation history into a living, searchable second brain.

You have months or years of conversations in Claude — architectural decisions, research sessions, debugging breakthroughs, strategy discussions. It's all locked in a linear export file, unsearchable, unlinked, and forgotten.

This 10-agent pipeline parses your Claude exports, extracts knowledge, and generates a fully organized Obsidian vault: bidirectional wikilinks, Maps of Content, topic clusters, and a knowledge graph that shows how your thinking connects across time.

---

## Features

- **10-agent parallel pipeline** — each agent does one job well: parse, clean, tag, analyze, link, cluster, write, generate MOCs, index, validate
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
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp config/settings.example.yaml config/settings.yaml
# Add your ANTHROPIC_API_KEY to config/settings.yaml

# 3. Export your Claude conversations
# claude.ai → Settings → Account → Export Data → Download

# 4. Run the pipeline
python -m src.main --input /path/to/claude-export.json --output ./my-second-brain

# 5. Open in Obsidian
# File > Open Vault > select "my-second-brain" folder
```

---

## Demo

```
$ python -m src.main --input claude-export.json --output ./brain

[01/10] Parser      Extracted 847 conversations (JSON format)
[02/10] Cleaner     Removed 23 duplicates, normalized encoding
[03/10] Tagger      Extracted 312 unique topics across all conversations
[04/10] Analyzer    Identified 1,204 key decisions and 389 action items
[05/10] Linker      Found 4,891 cross-references (threshold: 0.70)
[06/10] Clusterer   Formed 28 knowledge clusters
[07/10] Writer      Generated 847 markdown notes with frontmatter
[08/10] MOC Gen     Created 28 Maps of Content + master index
[09/10] Indexer     Built timeline, topic index, statistics page
[10/10] Validator   Checked 4,891 links — 0 broken

Done in 18 minutes. Vault ready at ./brain
Open it in Obsidian to explore your knowledge graph.
```

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
│  04 Analyzer → 05 Linker → 06 Clusterer     │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│             GENERATION LAYER                │
│  07 Writer → 08 MOC Gen → 09 Indexer        │
│                        → 10 Validator       │
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
| **04 Analyzer** | Identifies key decisions, insights, action items, code blocks |
| **05 Linker** | Finds semantic relationships for cross-linking |
| **06 Clusterer** | Groups related conversations using graph analysis |
| **07 Writer** | Generates markdown notes with frontmatter |
| **08 MOC Generator** | Creates Maps of Content per topic cluster |
| **09 Indexer** | Builds timeline, topic index, statistics pages |
| **10 Validator** | Checks broken links, validates frontmatter, QA |

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

| Export Size | Conversations | Time (4 parallel agents) |
|-------------|---------------|--------------------------|
| Small | < 100 | ~2 min |
| Medium | 100–500 | ~10 min |
| Large | 500–2000 | ~30 min |
| Very Large | 2000+ | ~1 hr |

---

## Exporting Your Claude Conversations

1. Go to [claude.ai](https://claude.ai)
2. **Settings** → **Account** → **Export Data**
3. Download the JSON or HTML export file
4. Pass it to `--input`

---

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
ruff check src/
mypy src/
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
