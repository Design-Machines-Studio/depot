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
- **Basic fields** — Text, rich text, assets, dates, toggles, links, colors, numbers
- **Specialized fields** — JSON (5.7), Range (5.5), Button Group (5.7), Content Block (5.8), Generated Fields (5.8)
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
**Groups** — Organize the "+ Add" menu (5.8+), searchable when 5+ types
**View mode:**
- Inline-editable blocks (traditional, visual, expand/collapse all in 5.8)
- Cards (cleaner, opens in slideout, bulk actions in 5.9, card grid option in 5.9)
- Element index (for large datasets, sortable by custom fields in 5.7)
**Versioning** — Matrix nested entries can have their own revisions (5.7)

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

Entry types can have descriptions (5.8) — useful as info tooltips in entry type chips. They can be duplicated with "Save as a new entry type" (5.8). Names and handles can be overridden per section or Matrix field (5.6).

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

## New Field Types (5.5–5.9)

### Content Block (5.8)
A new field type for structured content that lives within an entry. Unlike Matrix (which manages nested entries), Content Block is a simpler container. Cards and table views can now display fields nested within Content Block fields (5.9).

### Generated Fields (5.8)
Computed fields whose values are generated from other fields. Displayed in element indexes and sortable (5.9). Useful for combining fields (e.g., "Full Name" from first + last) or computed values.

### JSON Field (5.7)
Native JSON storage — useful for API responses, configuration objects, or structured data that doesn't map to Craft's field types.

### Button Group (5.7)
An alternative to Dropdown/Radio Buttons with a more compact visual display. Options support icons and colors (as do Dropdown, Radio Buttons, Checkboxes, and Multi-select since 5.7).

### Range Field (5.5)
Slider input for numeric values — good for ratings, percentages, or constrained numbers.

### Link Field Enhancements (5.5–5.9)
- Advanced fields: Target, URL Suffix, Title Text, ARIA Label, Class Name, ID, rel (5.6)
- SMS link type and custom URL schemes (5.7)
- Download option (5.7)
- Inline list and card grid view modes (5.9)
- GraphQL mode setting (5.6)

## Conditional Field Layouts (Craft 5)

Field tabs and individual fields can be conditionally shown based on:
- Entry type or section
- Custom field values (e.g., show "Video URL" only when format is "video")
- User group or status

This replaces the need for many single-purpose entry types. Instead of separate "Video Article" and "Text Article" types, use one "Article" type with conditional fields.

**When to use conditions vs separate entry types:**
- Conditions: Same core shape, minor variations
- Separate types: Fundamentally different content structures

**Editability conditions** (5.7): Individual fields can be made read-only based on conditions — useful for locking certain fields for specific user groups while keeping them visible.

**Field editability conditions** (5.9): Custom fields can now have editability conditions based on the edited element itself, not just user permissions.

## Author Experience (5.5–5.9)

### Entry Type Settings
- **UI Label Format** (5.9) — Control how entries are labeled in lists
- **Allow line breaks in titles** (5.9) — For entries that need multi-line titles
- **Descriptions** (5.8) — Appear as info tooltips on entry type chips
- **Title field optional** (5.5) — Title can be removed from field layout entirely; Default Title Format generates it

### Element Indexes
- **Multi-page sources** (5.9) — Entry sources can span multiple index pages
- **Collapsible source headings** (5.8) — Cleaner sidebar navigation
- **XLSX and YAML export** (5.9) — In addition to CSV

### Card Views
- **Card attributes** (5.5) — Include element attributes alongside custom fields
- **Thumbnail alignment** (5.8) — Customize thumbnail positioning in cards
- **Content Block field nesting** (5.9) — Cards can display nested Content Block fields

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
