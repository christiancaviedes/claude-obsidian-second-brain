# Contributing to Claude Obsidian Second Brain

Thanks for wanting to help. This project turns AI conversation history into something genuinely useful — contributions that improve that output quality are especially valuable.

## What We'd Love

- **Support for other AI exports** — ChatGPT, Gemini, Perplexity exports
- **New agent capabilities** — sentiment analysis, project timeline extraction, meeting note detection
- **Better linking algorithms** — improved semantic similarity for cross-references
- **Obsidian plugin** — for incremental imports without re-running the full pipeline
- **Web UI** — configuration and preview without touching YAML
- **Performance improvements** — faster processing for very large exports (2000+ conversations)
- **Bug reports** — especially around edge cases in JSON/HTML parsing

## How to Contribute

1. **Fork** the repo and create a branch: `git checkout -b feature/your-feature`
2. **Make your changes** — keep agents focused on their single responsibility
3. **Write tests**: `python -m pytest tests/ -v`
4. **Run linting**: `ruff check src/` and type checking: `mypy src/`
5. **Open a PR** with what you changed and a sample of output quality improvement (before/after notes if applicable)

## Development Setup

```bash
git clone https://github.com/christiancaviedes/claude-obsidian-second-brain.git
cd claude-obsidian-second-brain
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp config/settings.example.yaml config/settings.yaml
# Add your ANTHROPIC_API_KEY to config/settings.yaml
python -m pytest tests/ -v
```

## Agent Design Principles

Each agent should:
- Do exactly one thing
- Accept clean input, produce clean output
- Be independently testable
- Log its progress clearly

## Reporting Issues

Open an issue with:
- Python version and OS
- Export size (approx. conversation count)
- The command you ran
- Error output (with API keys removed)

## Questions

Open an issue with the `question` label.
