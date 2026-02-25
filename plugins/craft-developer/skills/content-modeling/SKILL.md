---
name: content-modeling
description: Content modeling methodology for Craft CMS projects. Use when designing content architecture, planning sections and fields, configuring Matrix fields, setting up CKEditor, or advising on content model decisions. Covers the three-layer approach (Foundation, Structure, Experience) and design system conventions.
---

# Content Modeling for Craft CMS

A methodology for designing content models that are flexible, author-friendly, and maintainable.

## The Three-Layer Approach

Content modeling is iterative. Instead of trying to design everything upfront, work in layers:

### Layer 1: Foundation
The building blocks. Things that exist independently.

- **Filesystems** — Where files physically live
- **Volumes** — How authors interact with files
- **Basic fields** — Text, rich text, assets, dates, toggles
- **Entry types** — The shapes of content (for sections and Matrix)

### Layer 2: Structure
Connect the foundation pieces.

- **Matrix fields** — Configure content builders
- **Sections** — Where entry types live (Singles, Channels, Structures)
- **CKEditor** — Rich text configuration
- **Relations** — Entries fields connecting content

### Layer 3: Experience
Refine for authors.

- **Field layouts** — Organization and grouping
- **Conditional fields** — Show/hide tabs and fields based on entry values (Craft 5)
- **Element indexes** — How content lists appear, custom sources with conditions
- **Validation** — Required fields, constraints
- **Card views** — How entries appear as cards

## Design System Conventions

### Naming Strategy

**Labels** — What authors see in the control panel
- Use sentence case
- Be clear and recognizable

**Handles** — What templates reference
- Use camelCase (Craft default)
- Keep consistent across similar fields

**Generic fields, semantic overrides:**
Create fields for field types, not content purposes:
- `richText` → override label to "Body", "Description", "Bio"
- `plainText` → override to "Heading", "Subhead", "Caption"
- `image` → override to "Hero Image", "Thumbnail", "Avatar"

### Color Strategy (Entry Types)

Use color to create visual hierarchy:

**Section entry types:**
- Warm colors for top-level content
- Cool colors for supporting content
- No-color for utility types

**Matrix block entry types:**
- Blues for text/written content
- Greens for media
- Warm colors for interactive elements
- No-color for structural containers

## Matrix Fields

### Configuration Essentials

**Entry types** — Which blocks are available
**Groups** — Organize the "+ Add" menu (Craft 5.8+)
**View mode:**
- Inline-editable blocks (traditional, visual)
- Cards (cleaner, opens in slideout)
- Element index (for large datasets)

### Nesting

Nesting is configured in entry type field layouts, not Matrix settings.

To enable nesting:
1. Add the Matrix field to an entry type's field layout
2. That entry type can now contain nested content

Example: Section block contains Content builder field → Section blocks can nest other blocks.

**Control what nests what:**
- Section block → can contain all blocks
- Grid block → only Grid Item blocks
- Content block → no children

### Entry Type Sharing

In Craft 5, entry types exist in a global pool:
- The same entry type can appear in multiple Matrix fields
- Entry types can be used in both sections and Matrix fields
- This means a "Quote" entry type works as a Matrix block AND as a standalone entry
- Changes to the entry type propagate everywhere it's used

**Plan for this:** Design entry types generically enough to reuse, but specific enough to be meaningful.

### One Matrix or Several?

Start with one Content builder Matrix. Split into specialized matrices when authors need clearer constraints.

## CKEditor Configuration

### When to Use CKEditor vs Matrix

**CKEditor embeds:**
- Document-style content
- Flowing text with occasional embedded elements
- Simpler sites
- Inline positioning matters

**Matrix blocks:**
- Layout-driven content
- Visual page structure
- Tight design control
- Authors manipulate page architecture

**Both together:**
- Matrix for page structure (sections, containers)
- CKEditor inside Content blocks for flowing text

### Configuration Approach

Create multiple configurations:
- **Simple** — Basic formatting (bold, italic, links, lists)
- **Full** — More options (headings, quotes, tables, embeds)

Less is more. Cluttered toolbars invite off-brand formatting.

## Sections

### Section Types

**Singles** — One entry, one purpose (homepage, settings)
**Channels** — Collections, order from queries (blog, products)
**Structures** — Hierarchical, manual ordering (pages, docs)

### Choosing the Right Type

Use a **Single** when:
- There's only ever one of this thing
- It doesn't belong in a collection

Use a **Channel** when:
- Multiple entries of the same type
- Order determined by data (date, title)
- No parent-child relationships

Use a **Structure** when:
- Order matters and authors control it
- Entries need hierarchy
- Building navigation or nested pages

## Relations

### Entries Fields

Use Entries fields to connect content:
- Articles → Author
- Products → Categories
- Case studies → Client

### Categories and Tags as Entries

Build Categories and Tags as entry types in their own sections. Use Entries fields for relationships. This is more flexible and is Craft's direction.

**Categories section** (Structure if hierarchical, Channel if flat)
**Tags section** (Channel, simple entry type)

### Relationship Direction

Craft doesn't create bi-directional relationships automatically. The data lives on the entry with the Entries field.

Query from either direction:
- From Article, access Topics directly
- From Topic, use `relatedTo` to find Articles

## Conditional Field Layouts (Craft 5)

Field tabs and individual fields can be conditionally shown based on:
- Entry type or section
- Custom field values (e.g., show "Video URL" only when format is "video")
- User group or status

This replaces the need for many single-purpose entry types. Instead of separate "Video Article" and "Text Article" types, use one "Article" type with conditional fields.

**When to use conditions vs separate entry types:**
- Conditions: Same core shape, minor variations
- Separate types: Fundamentally different content structures

## What You'll Discover

Working through layers reveals requirements:

- Matrix needs more blocks than planned
- Some blocks need nesting, others don't
- CKEditor can do more (or less) than expected
- Relations reveal missing entry types
- Content builder needs option fields (colors, layouts)

**This is expected.** Return to earlier layers as needed. That's the iterative process working correctly.

## Reference Files

For detailed patterns, see:
- `references/matrix-patterns.md`
- `references/ckeditor-patterns.md`
