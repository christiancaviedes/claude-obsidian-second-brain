---
title: Timeline
type: moc
created: {{date}}
---

# Conversation Timeline

A chronological view of all your Claude conversations.

## How to Navigate

- **By Year**: Jump to a specific year section below
- **By Month**: Each year contains monthly groupings
- **Search**: Use Cmd/Ctrl + Shift + F to search across all dates
- **Dataview**: Use the queries below for dynamic date filtering

## Timeline Structure

### 2024

#### December 2024
```dataview
LIST
FROM "001 Conversations"
WHERE file.ctime >= date(2024-12-01) AND file.ctime < date(2025-01-01)
SORT file.ctime DESC
```

#### November 2024
```dataview
LIST
FROM "001 Conversations"
WHERE file.ctime >= date(2024-11-01) AND file.ctime < date(2024-12-01)
SORT file.ctime DESC
```

#### October 2024
```dataview
LIST
FROM "001 Conversations"
WHERE file.ctime >= date(2024-10-01) AND file.ctime < date(2024-11-01)
SORT file.ctime DESC
```

*(Earlier months follow the same pattern)*

## Recent Conversations

Last 7 days:
```dataview
TABLE file.ctime as "Date", length(file.outlinks) as "Links"
FROM "001 Conversations"
WHERE file.ctime >= date(today) - dur(7 days)
SORT file.ctime DESC
```

## This Month

```dataview
TABLE file.ctime as "Date"
FROM "001 Conversations"
WHERE file.ctime >= date(sow) - dur(30 days)
SORT file.ctime DESC
LIMIT 20
```

## Conversation Statistics by Month

```dataview
TABLE length(rows) as "Conversations"
FROM "001 Conversations"
GROUP BY dateformat(file.ctime, "yyyy-MM")
SORT rows[0].file.ctime DESC
```

---

*Return to [[README|Index]]*
