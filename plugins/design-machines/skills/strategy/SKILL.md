---
name: strategy
description: Design Machines business strategy, product positioning, catalog system, Assembly architecture, partnership ecosystem, revenue model, and brand language. Use when working on DM business planning, product naming, pricing, client conversations, partnership coordination, marketing copy, catalog entries, or any strategic decision about Design Machines OÜ. Also use when context about Travis Gertz's positioning, target market, or competitive landscape is needed.
---

# Design Machines Strategy Skill

Business strategy and product intelligence for Design Machines OÜ. Company details (registration, location, tax structure) are stored in ai-memory — search for "Design Machines OÜ".

## Mission

Design Machines exists to democratize the workplace. We use design, systems thinking, and operations to make it easy to start and run democratic organizations like worker-owned cooperatives.

## Elevator Pitch

Governance is the part of running a co-op that nobody wants to do. It's boring. It's confusing. And if you mess it up, you're not really a co-op anymore. I build systems that make governance simple. Even enjoyable. So people can focus on the work they actually started the co-op to do.

## Positioning Statement

**For** small worker cooperatives struggling with governance, **Assembly** is a bespoke operations system **that** makes running a co-op simple and even enjoyable. **Unlike** spreadsheets, generic business tools, or expensive enterprise solutions, **I** build purpose-built systems informed by years of actually running a worker co-op.

---

## Product Family

| Code | Name | Type | Status | What It Does |
|------|------|------|--------|--------------|
| DM-005 | **Assembly** | Works | Prototype | Bespoke governance OS for worker co-ops |
| DM-003 | **Live Wires** | Works | Beta | Typography-first CSS framework for editorial web |
| — | **Nimber** | Works | Legacy/Future | Rate setting & estimation for agencies |

**Assembly** is the flagship. **Live Wires** is secondary but strategically important as the top of the conversion funnel. **Nimber** is future consideration.

### Assembly Architecture

```
Assembly (product line)
├── Baseplate — core application starter (every co-op starts here)
├── Fixtures — modules that bolt on
│   ├── Governance (meetings, resolutions, proposals, decisions)
│   ├── Members (directory, roles, onboarding, lifecycle)
│   ├── Equity (shares, ICAs, patronage, redemption)
│   ├── Compensation (factor-based salary framework)
│   └── Documentation (SOPs, manuals, knowledge base)
└── [Client Name] — whatever the co-op calls theirs
    └── Each co-op names their own install
```

**Naming logic:**
- **Assembly** = factory assembly (making things) + democratic assembly (deciding things)
- **Baseplate** = machinery mounting plate. Everything bolts to it.
- **Fixtures** = manufacturing jigs that configure machines for specific work
- **Client naming**: Each co-op names their own install. It's theirs, not ours.

**Tech stack:** Go backend + Datastar (real-time SSE) + Live Wires CSS + SQLite (modular) + Templ templates

### Live Wires Positioning

"The CSS framework built for content-heavy websites, where typography comes first, class names make sense to editors, and prototypes evolve into production code."

Key differentiators vs Tailwind: semantic classes, typography-first, no utility soup, CMS-friendly naming.

### The Conversion Funnel

Designer uses Live Wires → encounters labor/AI content → learns about co-ops → becomes Assembly client. Products catch at craft level, co-op work catches at values level.

---

## DM Catalog System

Inspired by Factory Records' FAC numbering. Everything is a release. A CSS framework sits next to a conference talk sits next to a governance system.

### Current Catalog

| Code | Name | Category | Status |
|------|------|----------|--------|
| DM-000 | "Design Machines" essay | /PRESS | Origin · 2015 |
| DM-001 | Design Machines OÜ | Company | Active · 2024 |
| DM-002 | "AI or Bust(ed)" | /FLOOR | Dot All 2024 |
| DM-003 | Live Wires | /WORKS | Beta |
| DM-004 | The Northern Star | /PLATE | Demo site |
| DM-005 | Assembly | /WORKS | Prototype |

### Category Markers

| Marker | Meaning | Covers | Source |
|--------|---------|--------|--------|
| /WORKS | Products & tools | Frameworks, applications, calculators | Factory works (ironworks, steelworks) |
| /PLATE | Templates & starters | Starter kits, themes, components | Printing plates (reusable forms) |
| /PRESS | Publications | Essays, guides, books, courses | The printing press; "the press" |
| /FLOOR | Talks & events | Conference talks, workshops, podcasts | The shop floor; "you have the floor" |

Markers are optional. DM-003 works alone. DM-003/WORKS adds clarity. Number is canonical.

### Rules

- Sequential numbering, chronological by catalog entry
- Codes always public — on product pages, slides, invoices
- Printed small, monospaced, consistent position
- Reserved numbers for milestones (DM-051, DM-100)

---

## Target Market

### Primary: Small Worker Cooperatives (5-50 members)

People who:
- Are maturing past startup phase, hitting governance growing pains
- Started without deep cooperative experience
- Care about doing it right — values-driven
- Have access to grants or can match funding

### Market Segments

| Segment | Priority | Entry Point |
|---------|----------|-------------|
| Existing worker co-ops | Primary | Co-op developers, federations |
| New co-ops | High | Co-op incubation pipelines |
| Platform cooperatives | Underserved | Tech-literate, better funded |
| Conversion market | Long-term | Live Wires → labor content → co-ops |

### Not the Customer (for now)

Large established co-ops with own systems. Co-ops with no budget and no path to funding. Traditional businesses wanting a website.

---

## Revenue Model

### Project-Based Engagements

Assembly projects cover Discovery + Design, Implementation, and Training phases with optional maintenance retainers. Pricing details are stored in ai-memory — search for "Assembly" or check `references/revenue.md`.

### Funding Sources

Co-op direct payment, federation grants, credit union community development funds, co-op matching funds. Partner network knows the funding landscape.

### Financial Targets

Current financial targets, runway, and burn rate are stored in ai-memory — search for "Design Machines OÜ".

---

## Partnership Ecosystem

### The Emerging Stack

| Layer | What |
|-------|------|
| Financial Foundation | Bookkeeping, cash flow, pricing tools for co-ops |
| Governance Interface | Decisions, members, equity, democracy UX (Assembly) |
| Real-time Collaboration | Live state sync, SSE for voting and dashboards |
| Design System | Typography-first CSS, editorial design (Live Wires) |

### Key Partners

Current partner details and pipeline status are stored in ai-memory. Search for partner names or "Design Machines" relationships. See `references/partnerships.md` for partner archetypes and ecosystem structure.

### Current Pipeline

Active pipeline details (specific clients, meeting dates, status) are stored in ai-memory. See `references/pipeline.md` for distribution channels and pilot criteria.

---

## Operating Principles

1. **Products, not services.** Build once, sell many. No trading hours for dollars.
2. **Slow and intentional.** Compound over years, not months.
3. **Charge from day one.** Validate with revenue, not vanity metrics.
4. **Build for yourself.** The customer is someone like you.
5. **Stay small, stay profitable.** Basecamp model, not VC model.

---

## Brand Language Territory

Every name and piece of marketing must feel like it belongs to at least one of three worlds:

**Factories** (how things are made) + **Labor** (who makes them and under what conditions) + **Publishing** (how ideas spread)

### The Naming Test

Before naming anything: **Can I picture this in a factory, a union hall, or a print shop?** If yes, it fits. If it sounds like a SaaS landing page, start over.

### Word Banks

**Factory & Industrial:** Anvil · Bellows · Forge · Gauge · Jig · Lathe · Loom · Press · Proof · Spindle · Voltage · Workbench

**Labor & Democracy:** Ballot · Charter · Dispatch · Guild · Ledger · Local · Mandate · Muster · Quorum · Roll Call · Steward · Union Hall

**Publishing & Editorial:** Broadsheet · Byline · Chapbook · Colophon · Folio · Galley · Imprint · Leaflet · Masthead · Newsprint · Typeset · Woodcut

---

## Go-to-Market: The Trojan Horse

Lead with internal operations, not public-facing design.

**Why:**
- Co-ops can get funding for operations infrastructure more easily than marketing websites
- Focuses clients on functionality, bypasses subjective aesthetic debates
- Design language gets established as side effect → public website extension later is cheap
- Internal system itself is propaganda — modern operations make co-ops less scary to outsiders

**Channels:**
- Co-op incubation pipelines (new co-ops twice yearly)
- Co-op developers and meta co-ops
- Provincial and national co-op federations — grant money and referral networks
- Credit unions as funders AND clients
- Content: blog, YouTube, resources
- Speaking: co-op conferences, design conferences

---

## Competitive Landscape

**What co-ops actually use today:** Spreadsheets, Google Docs, Notion (if technical), generic tools (Monday, Asana), paper, nothing at all, expensive custom solutions ($50K+).

**The real competition:** Cobbled-together free tools plus hope.

---

## Reference Files

Load specific reference files based on needs:

| Topic | Reference File | When to Load |
|-------|----------------|--------------|
| DM Catalog system | `references/catalog.md` | Naming new products, catalog entries |
| Assembly architecture | `references/assembly.md` | Technical discussions, scoping |
| Partnerships | `references/partnerships.md` | Partner coordination, pipeline |
| Revenue model | `references/revenue.md` | Pricing, proposals, financial planning |
| Brand language | `references/brand-language.md` | Naming, copy, marketing |
| Pipeline & pilots | `references/pipeline.md` | Client conversations, preparation |
