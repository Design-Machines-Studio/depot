# Assembly -- Product Architecture Reference

## What Assembly Is

A governance system configured to each worker co-op's bylaws. Assembly is in beta, selling and installing. Check ai-memory entity "Assembly" for release dates and current state.

## Architecture

Governance and Atlas are shipped fixtures on Baseplate. Check ai-memory entity "Assembly" for release dates and current install state.

```
Assembly (product line)
├── Baseplate: core application starter, including the thread primitive
├── Fixtures: modules that bolt on
│   ├── Governance: shipped; proposals, decisions, decision log
│   ├── Atlas: shipped; network view for federations and incubators
│   ├── Discussions: prototyped, shipping next; included with Baseplate
│   ├── Money: prototyped, after Discussions; bank-balance forecasting
│   └── Switchboard: fixture for entitlements and the operator model
└── [Client Name]: each co-op names its own install
```

Baseplate provides authentication, navigation, member profiles and basic settings. Each co-op has its own fixture configuration.

Atlas shows member organisations, people and positions counts, a head-office map and configurable stat cards. Networks can manually add non-Assembly co-ops, invite them and merge their records when they connect.

Discussions is forum-style and topic-first, with no upvotes or direct messages. Its thread primitive lives in Baseplate so proposals can have discussions without the fixture. Money forecasts bank balances from near to far and checks forecast accuracy against actuals with minimal data entry. It is not accounting.

Meetings and the minute book will likely become separate fixtures later. Members, Equity, Compensation and Documentation are unbuilt as separate fixtures. Baseplate already holds member identity and profiles.

### Installs

- **Design Machines** is the internal install where the team runs its own governance.
- **Assembly Hall** (`hall.asmbly.app`) is the shared community install for partners. It is the demo, the feedback channel and the place partners meet each other.
- **Demo** is a separate install that resets nightly.

Community lives in Assembly Hall. The former DM-019 community service is retired from strategy; check ai-memory for the retirement history.

## Naming Logic

**Assembly** -- Factory assembly (making things) + democratic assembly (deciding things). Both meanings describe the product. As a product line, it's literally correct -- you assemble Fixtures onto a Baseplate.

**Baseplate** -- The mounting plate in machinery. Everything bolts to it. A /PLATE in the catalog -- a reusable form that produces many unique outputs.

**Fixtures** -- In manufacturing, fixtures attach to a baseplate to configure it for specific work. Same baseplate, different fixtures, different capabilities.

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

## Integration Boundary

ATProto sign-in is a paid integration behind the organisation-identity seam. Keep integration work separate from governance discovery and the Install. A partner pays for a prerequisite integration before Design Machines builds it. Check ai-memory for current requests and funding state.

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
| Enterprise solutions priced for large co-ops | Grant-sized Install, annual Plan and additional Fixtures; figures in ai-memory |
| Software you install and figure out | Consultation + training + bespoke system |
| Compliance-feeling bureaucratic interfaces | Designed to feel good, simple, expressive |
| Static request-response interfaces | Real-time collaboration, live voting, instant updates |

## Design Principles

1. **Two audience design**: Worker-members need simplicity; compliance-savvy members need precision
2. **Progressive disclosure**: Show complexity only when needed
3. **Contextual education**: Learn through use, not upfront training
4. **Inhabited interfaces**: Living rhythm, not archived snapshots
5. **Decolonial language**: Solidarity economy terminology for members, legal compliance for regulators

## Distribution and Hosting

Assembly is closed and source-available under licence to the right partners. It is not open source. A future fixture marketplace would sell Design Machines fixtures with at most a few vetted partners. It is not a current priority.

White-label managed hosting is fulfilled by hosting partners such as Arcustech and Cantrust. The host answers for the server; Design Machines answers for the app. Self-hosting is undecided. Confirm the hosting arrangement before go-live; check ai-memory for partner agreements and current hosting state.
