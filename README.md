[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/yourusername/claude-obsidian-second-brain.svg?style=social)](https://github.com/yourusername/claude-obsidian-second-brain)

# Claude Obsidian Second Brain

**Transform your Claude conversation history into a searchable, linked Obsidian Second Brain — automatically.**

A 10-agent pipeline that parses your Claude exports, extracts knowledge, and generates a beautifully organized Obsidian vault with bidirectional links, topic clustering, and Maps of Content.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Claude Export (JSON/HTML)                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INGESTION LAYER                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                      │
│  │  01 Parser  │───▶│  02 Cleaner │───▶│  03 Tagger  │                      │
│  │             │    │             │    │             │                      │
│  │ JSON/HTML   │    │ Normalize   │    │ Extract     │                      │
│  │ extraction  │    │ & dedupe    │    │ topics/tags │                      │
│  └─────────────┘    └─────────────┘    └─────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ANALYSIS LAYER                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                      │
│  │ 04 Analyzer │───▶│ 05 Linker   │───▶│ 06 Clusterer│                      │
│  │             │    │             │    │             │                      │
│  │ Key points, │    │ Find cross- │    │ Group by    │                      │
│  │ decisions   │    │ references  │    │ knowledge   │                      │
│  └─────────────┘    └─────────────┘    └─────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          GENERATION LAYER                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ 07 Writer   │───▶│ 08 MOC Gen  │───▶│ 09 Indexer  │───▶│ 10 Validator│  │
│  │             │    │             │    │             │    │             │  │
│  │ Markdown    │    │ Maps of     │    │ Timeline &  │    │ Link check  │  │
│  │ with YAML   │    │ Content     │    │ topic index │    │ & QA        │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Obsidian Vault (Ready to Use)                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## What You Get

- **A beautifully organized Obsidian vault** — ready to open and explore immediately
- **Auto-generated Maps of Content (MOCs)** — for every major topic discovered in your conversations
- **Rich frontmatter on every note** — date, topics, key decisions, action items, and source metadata
- **Bidirectional `[[wikilinks]]`** — automatically linking related conversations and concepts
- **Knowledge cluster visualization** — see how your ideas connect in Obsidian's graph view
- **Chronological timeline** — browse your conversations by date with contextual summaries
- **Topic frequency index** — discover what you discuss most and track knowledge growth
- **Clean, readable Markdown** — no proprietary formats, your data stays portable

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Python** | 3.10 or higher ([download](https://www.python.org/downloads/)) |
| **Obsidian** | Free, cross-platform ([download](https://obsidian.md/)) |
| **Anthropic API Key** | For AI-powered analysis ([get key](https://console.anthropic.com/)) |
| **Claude Export** | Your conversation history (JSON or HTML format) |

### Exporting Your Claude Conversations

1. Go to [claude.ai](https://claude.ai)
2. Navigate to **Settings** > **Account** > **Export Data**
3. Download your export (you'll receive a JSON or HTML file)

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/claude-obsidian-second-brain.git
cd claude-obsidian-second-brain

# 2. Set up your environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure your API key
cp config/settings.example.yaml config/settings.yaml
# Edit config/settings.yaml and add your ANTHROPIC_API_KEY

# 4. Run the pipeline
python -m src.main --input /path/to/claude-export.json --output ./my-second-brain

# 5. Open in Obsidian
# File > Open Vault > Select "my-second-brain" folder
```

---

## Configuration

Edit `config/settings.yaml` to customize the pipeline:

```yaml
# API Configuration
anthropic:
  api_key: ${ANTHROPIC_API_KEY}  # Or set directly (not recommended)
  model: claude-sonnet-4-20250514  # Model for analysis agents

# Input/Output
paths:
  input: ./exports/claude-export.json
  output: ./my-second-brain
  
# Processing Options
pipeline:
  parallel_agents: 4          # Number of agents to run concurrently
  batch_size: 50              # Conversations per batch
  skip_short: true            # Skip conversations under 3 exchanges
  min_exchanges: 3            # Minimum exchanges to process

# Vault Structure
vault:
  index_folder: "000 Index"
  topics_folder: "Topics"
  conversations_folder: "Conversations"
  daily_notes: true           # Generate daily note links
  
# Analysis Settings
analysis:
  extract_code_blocks: true   # Create separate notes for significant code
  extract_action_items: true  # Pull out TODOs and action items
  link_threshold: 0.7         # Similarity threshold for auto-linking (0-1)
  
# MOC Generation  
moc:
  min_notes: 3                # Minimum notes to generate a MOC
  max_depth: 2                # Nesting depth for topic hierarchy
```

---

## Example Vault Structure

```
my-second-brain/
├── 000 Index/
│   ├── README.md                    # Vault welcome & navigation
│   ├── Topics MOC.md                # Master map of all topics
│   ├── Timeline.md                  # Chronological conversation list
│   └── Statistics.md                # Knowledge metrics & insights
│
├── Topics/
│   ├── Coding/
│   │   ├── Coding MOC.md            # Map of all coding conversations
│   │   ├── Python/
│   │   │   └── Python MOC.md
│   │   ├── APIs/
│   │   │   └── APIs MOC.md
│   │   └── Debugging/
│   │       └── Debugging MOC.md
│   │
│   ├── Strategy/
│   │   ├── Strategy MOC.md
│   │   ├── Product Planning/
│   │   └── Decision Frameworks/
│   │
│   └── Learning/
│       ├── Learning MOC.md
│       └── Mental Models/
│
├── Conversations/
│   ├── 2024-01-15 Building a REST API.md
│   ├── 2024-01-18 React Component Architecture.md
│   ├── 2024-02-03 Startup Pricing Strategy.md
│   └── ...
│
├── Action Items/
│   └── Open Tasks.md                # Aggregated action items
│
└── Code Snippets/
    ├── Python/
    │   └── async_retry_decorator.md
    └── JavaScript/
        └── react_custom_hook.md
```

---

## The 10 Agents

| # | Agent | Purpose |
|---|-------|---------|
| **01** | Parser | Ingests JSON/HTML exports, extracts conversation structure and metadata |
| **02** | Cleaner | Normalizes text, removes duplicates, handles encoding issues |
| **03** | Tagger | Uses Claude to extract topics, categories, and semantic tags |
| **04** | Analyzer | Identifies key decisions, insights, action items, and code blocks |
| **05** | Linker | Finds semantic relationships between conversations for cross-linking |
| **06** | Clusterer | Groups related conversations into knowledge clusters using graph analysis |
| **07** | Writer | Generates clean Markdown files with proper frontmatter and formatting |
| **08** | MOC Generator | Creates Maps of Content for each topic cluster |
| **09** | Indexer | Builds timeline, topic index, and statistics pages |
| **10** | Validator | Checks for broken links, validates frontmatter, ensures vault integrity |

Each agent is designed to do one thing well, with clear inputs and outputs. The pipeline coordinates them to process your export efficiently, with configurable parallelism for larger exports.

---

## Performance

| Export Size | Conversations | Processing Time* |
|-------------|---------------|------------------|
| Small | < 100 | ~2 minutes |
| Medium | 100-500 | ~10 minutes |
| Large | 500-2000 | ~30 minutes |
| Very Large | 2000+ | ~1 hour |

*Times vary based on conversation length, API rate limits, and `parallel_agents` setting.

---

## Contributing

Contributions are welcome! Here's how to help:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Make** your changes with tests
4. **Run** the test suite (`python -m pytest tests/`)
5. **Commit** your changes (`git commit -m 'Add amazing feature'`)
6. **Push** to the branch (`git push origin feature/amazing-feature`)
7. **Open** a Pull Request

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/ -v

# Run linter
ruff check src/

# Run type checker
mypy src/
```

### Ideas for Contribution

- Additional export format support (ChatGPT, other AI assistants)
- Custom tagging taxonomies
- Obsidian plugin for incremental imports
- Web UI for configuration
- Advanced graph analysis algorithms

---

## Troubleshooting

**"API key not found"**
- Ensure `ANTHROPIC_API_KEY` is set in your environment or `config/settings.yaml`

**"Export file not recognized"**
- Verify you have a valid Claude export (JSON or HTML format)
- Check the file isn't corrupted or truncated

**"Too many API requests"**
- Reduce `parallel_agents` in settings
- The pipeline includes automatic rate limiting, but large exports may need patience

**"Missing links in vault"**
- Run the Validator agent: `python -m src.agents.validator --vault ./my-second-brain`
- Check the validator report for specific issues

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- Built with the [Anthropic API](https://www.anthropic.com/) and [Claude](https://claude.ai)
- Designed for [Obsidian](https://obsidian.md/) — the best tool for connected thinking
- Inspired by the Zettelkasten method and digital garden philosophy

---

<p align="center">
  <i>Transform your conversations into lasting knowledge.</i>
</p>
