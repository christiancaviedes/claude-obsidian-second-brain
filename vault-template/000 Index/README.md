# Welcome to Your Second Brain

Your personal knowledge vault powered by Claude AI conversations.

## Quick Navigation

- [[Topics MOC]] - Browse by topic and category
- [[Timeline]] - View conversations chronologically
- [[Projects MOC]] - Project-specific knowledge
- [[People MOC]] - Contacts and collaborators

## How to Use This Vault

### Finding Information
1. **Search** (Cmd/Ctrl + O): Quick search across all notes
2. **Graph View** (Cmd/Ctrl + G): Visualize connections between ideas
3. **Backlinks**: See what links to the current note in the right sidebar

### Organization
- **000 Index/**: Navigation and maps of content (MOCs)
- **001 Conversations/**: Individual Claude conversations
- **002 Topics/**: Topic-based knowledge summaries
- **003 Projects/**: Project-specific information
- **004 Resources/**: Code snippets, templates, references

### Key Maps of Content (MOCs)
- [[Topics MOC]] - All topics organized by category
- [[Timeline]] - Chronological conversation history
- [[Projects MOC]] - Active and archived projects
- [[Code Snippets]] - Reusable code and commands

## Recent Activity

```dataview
TABLE file.ctime as "Created", file.mtime as "Modified"
FROM "001 Conversations"
SORT file.mtime DESC
LIMIT 10
```

## Vault Statistics

```dataview
TABLE length(rows) as "Count"
FROM ""
GROUP BY file.folder
SORT length(rows) DESC
```

---

*This vault was generated from your Claude AI conversations using [claude-obsidian-second-brain](https://github.com/your-repo/claude-obsidian-second-brain).*
