# Notion API Conventions & Quirks

Rules and gotchas for working with Travis's Notion databases via MCP tools.

---

## Relation Properties

### Setting relations on page creation

Relations **cannot** be set when creating pages via `create-pages`. The Notion MCP tool ignores relation values in the properties object during creation.

**Correct workflow:**
1. Create the page with non-relation properties
2. Update the page with relation values in a second call

### Relation value format

Use bare URL strings when setting relations via `update-page`:

```
"Project": "https://www.notion.so/{project-page-id}"
```

**Do NOT use:**
- JSON arrays: `["https://www.notion.so/..."]`
- Page IDs alone: `"{page-id-with-dashes}"`

### Limit-1 relations

Sprint relations on Todos and Time Tracking entries are limit-1 — they accept only one sprint. Setting a new value replaces the old one.

---

## Date Properties

Use the expanded format for date properties:

```
"date:Date:start": "2026-02-13"
"date:Date:is_datetime": 0
```

For date ranges (like sprint Dates):

```
"date:Dates:start": "2026-02-16"
"date:Dates:end": "2026-02-27"
"date:Dates:is_datetime": 0
```

---

## Status Properties

Status is a special property type. Set it with the status name as a string:

```
"Status": "In progress"
```

Valid values are defined per database — see databases.md for each.

---

## Querying Databases

Use the Notion MCP `search` tool with `data_source_url` to query specific databases:

```
data_source_url: "collection://{todos-db-id}"
query: "sprint 4 todos"
```

For finding the active sprint:
```
data_source_url: "collection://{sprints-db-id}"
query: "in progress"
```

---

## Error Handling

- If a relation update fails, check the URL format (bare string, not array)
- If a page creation seems to lose properties, check if they were relation type (need second call)
- If status update fails, verify the exact status name matches (case-sensitive)
- Notion API rate limits: generally not an issue for session workflow, but avoid loops that hammer the API

---

## Number Properties

Use JavaScript numbers, not strings:

```
"Days": 0.25    ✅
"Days": "0.25"  ❌
```
