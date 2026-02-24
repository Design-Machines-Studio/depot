# Assembly — Product Architecture Reference

## What Assembly Is

A bespoke operations system for worker cooperatives. Custom-built for each organization. Not an off-the-shelf product. Not a SaaS subscription. Something the co-op owns and can run forever.

## Architecture

```
Assembly (product line — DM-005/WORKS)
├── Baseplate — the core application starter
│   Every co-op starts from the same Baseplate.
│   Authentication, navigation, member profiles, basic settings.
│
├── Fixtures — the modules that bolt on
│   No two co-ops have the same Fixtures configuration.
│   ├── Governance
│   │   Meeting minutes, resolutions, proposals, decision tracking.
│   ├── Members
│   │   Team directory, roles, onboarding flows, member lifecycle.
│   ├── Equity
│   │   Share ledger, Internal Capital Accounts, patronage tracking.
│   ├── Compensation
│   │   Factor-based salary framework. Location, experience, capacity.
│   └── Documentation
│       SOPs, manuals, knowledge base, policy version control.
│
└── [Client Name] — whatever the co-op calls theirs
    The co-op names their finished system. The name is theirs, not ours.
    Each co-op names their own install.
```

## Naming Logic

**Assembly** — Factory assembly (making things) + democratic assembly (deciding things). Both meanings describe the product. As a product line, it's literally correct — you assemble Fixtures onto a Baseplate.

**Baseplate** — The mounting plate in machinery. Everything bolts to it. A /PLATE in the catalog — a reusable form that produces many unique outputs.

**Fixtures** — In manufacturing, fixtures attach to a baseplate to configure it for specific work. Same baseplate, different fixtures, different capabilities.

## Internal vs Client Language

| Context | Language |
|---------|----------|
| Internal | "We're building their Assembly." |
| Internal | "Start from Baseplate, configure their Fixtures." |
| Internal | "The Governance Fixture needs customizing for their bylaws." |
| Client-facing | "[Co-op Name] is your operations hub." |
| Client-facing | "[Co-op Name] OS is built on the Assembly platform." |
| Client-facing | "Your system. Your name. Your democracy." |

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Go | Lightweight, fast, single binary deployment |
| Real-time | Datastar (SSE) | Live voting, collaborative decisions, no React/Vue complexity |
| Frontend CSS | Live Wires | Typography-first, editorial sensibility, CMS-friendly |
| Database | SQLite (modular) | One DB per module, simple deployment, portable |
| Templates | Templ | Go-native HTML templating, type-safe |

## Module Tiers

**MVP Tier** (Essential for pilot):
- Members module (profiles, classes, lifecycle)
- Governance module (basic decisions, meetings)
- Records & Compliance (statutory registers)
- Calendar & Reminders (annual rhythm)

**Core Tier** (Standard implementation):
- Equity module (shares, ICAs, redemption)
- Documentation (policies, version control)
- Advanced Governance (proposals, workflows)

**Advanced Tier** (Full implementation):
- Compensation (factor-based salary framework)
- Real-time features (live voting, collaboration via Datastar)
- Integrations (financial systems, partner tools)

## The "Journey Through a Year" Paradigm

Co-op governance isn't a dashboard you check occasionally. It's a rhythm.

| Frequency | What Happens |
|-----------|-------------|
| Daily | Pending proposals, action items |
| Weekly | Meeting preparation, decision tracking |
| Monthly | Member meetings, board meetings, operational reviews |
| Quarterly | Financial reviews, compliance checks |
| Annually | AGM, elections, audit, patronage allocation, annual report |

## What Makes Assembly Different

| What Others Do | What Assembly Does |
|----------------|-------------------|
| Generic tools forced into co-op shapes | Purpose-built for cooperative governance |
| Enterprise solutions priced for large co-ops | Accessible to small co-ops ($5K–50K) |
| Software you install and figure out | Consultation + training + bespoke system |
| Compliance-feeling bureaucratic interfaces | Designed to feel good, simple, expressive |
| Static request-response interfaces | Real-time collaboration, live voting, instant updates |

## Existing Assets

| Asset | Status |
|-------|--------|
| Notion prototype (14 database tables) | Complete — ran a real co-op for 4 years |
| Video walkthroughs (4 Loom recordings) | Complete |
| Module architecture (tiers defined) | Complete |
| Live Wires frontend CSS | Beta |
| Requirements checklist (150+ items, 8 modules) | Complete |

## Design Principles

1. **Two audience design**: Worker-members need simplicity; compliance-savvy members need precision
2. **Progressive disclosure**: Show complexity only when needed
3. **Contextual education**: Learn through use, not upfront training
4. **Inhabited interfaces**: Living rhythm, not archived snapshots
5. **Decolonial language**: Solidarity economy terminology for members, legal compliance for regulators

## Distribution Model

Assembly follows the **ONCE model** (37signals) — clients buy and own their install. Three-phase rollout:

1. **Phase 0 (Pilot)**: Manual Docker deploy. All fixtures compiled in, toggled at runtime. Design Machines deploys directly.
2. **Phase 1 (Self-Updating)**: Static registry with signed binaries. One-click updates. Lightweight Mothership dashboard.
3. **Phase 2 (Platform)**: Builder service compiles per-client binaries. Fixture marketplace. License management.

Full specification: `docs/DISTRIBUTION.md`, `docs/PILOT-SCOPE.md`, `docs/UPDATE-FLOW.md` in the Assembly repo.
