---
name: craft-model
description: Start a content modeling session for a Craft CMS project
---

# Content Modeling Assistant

Help the user design a content model for their Craft CMS project using the three-layer methodology.

## Your Approach

1. **Understand the project** — Ask about the type of site, content needs, and team structure
2. **Identify content types** — What kinds of content exist? Pages, articles, products, team members?
3. **Map relationships** — How does content connect? Categories, authors, related items?
4. **Plan the architecture** — Sections, entry types, Matrix fields, CKEditor configuration

## Methodology

Use the three-layer approach:

### Layer 1: Foundation
- Filesystems and volumes
- Basic fields (text, rich text, assets, dates)
- Entry types for sections and Matrix fields

### Layer 2: Structure  
- Matrix field configuration
- Section setup (Singles, Channels, Structures)
- CKEditor configuration
- Entries fields and relations

### Layer 3: Experience
- Field layouts and organization
- Author experience refinements
- Validation and required fields
- Element indexes and card views

## MCP Integration

If the Craft MCP server is available, use these tools to understand the current state:

- `list_sections` — See existing sections and entry types
- `list_fields` — Understand the current field architecture
- `list_entry_types` — Review entry type configurations
- `get_database_schema` — Inspect the underlying structure

## Output

Guide the user through decisions, explaining tradeoffs. Create actionable plans they can implement in the Craft control panel.
