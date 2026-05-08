# UI Design Patterns Reference

Practical UI patterns for evaluating and building modern SaaS interfaces. Every "good" example uses Live Wires vocabulary. Every "bad" example shows the amateur equivalent.

**How to use this reference:** When evaluating UI, check the rendered output against the patterns below. When recommending fixes, use the Live Wires implementation shown in "Good." Never recommend raw CSS values, manual flexbox, or invented class names.

**Benchmark products:** Stripe Dashboard, Notion, Linear, Figma, Vercel, Apple HIG, Shopify Polaris

---

## 1. Dashboard Patterns

**Stat Cards**

Good: `.grid` + `.box` with semantic scheme for each card. Status value in `.text-2xl font-bold`, label in `.text-sm`. Change indicators use `.badge--success` or `.badge--error`.

Bad: Manual `display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px`. Hardcoded card backgrounds. Inconsistent padding across cards.

**Activity Feeds**

Good: `.stack` for the feed, `.cluster cluster-compact` for each entry's metadata (avatar + name + timestamp). Timestamps in `.text-sm`. Dividers between entries using `.divider--hairline`.

Bad: Manual `margin-bottom` on each entry. No consistent spacing. Timestamps same size as content.

**Status Indicators**

Good: `.status-indicator--success` / `--warning` / `--error` for dot indicators. `.badge--active` / `--draft` / `--archived` for labeled status. Colors from semantic tokens.

Bad: Colored circles with hardcoded hex. Inconsistent size between status dots. Status text without visual indicator.

Benchmark: Stripe -- clean stat cards with subtle borders, clear hierarchy, sparkline charts in context.

---

## 2. List and Table Patterns

**Data Tables**

Good: `<table>` with `.table--lined` or `.table--striped`. Row hover via CSS (no JS needed). Sortable headers indicate direction with icon + `data-sort="asc"`. Bulk selection via checkbox column. Actions in last column, right-aligned.

Bad: `<div>` grid pretending to be a table. No hover states. Sort indicators missing. Actions scattered inconsistently.

**Empty States**

Good: Centered in a `.stack` with illustration or icon, descriptive text, and a primary CTA button (`.button button--accent`). The empty state should explain what will appear here and how to create the first item.

Bad: Just the text "No items found." No CTA. No explanation. No visual interest.

**Pagination**

Good: `.pagination` component with clear current-page indicator via `data-state="active"`. Show total count. Consider "Load more" button for feeds vs numbered pagination for searchable lists.

Bad: Just "Previous / Next" links. No page count. No indication of current position.

**Filtering**

Good: Filter controls in a `.cluster` above the table. Active filters shown as removable `.badge` pills. Filter state reflected in URL for shareability.

Bad: Filters in a separate panel that covers content. No indication of active filters. State lost on page refresh.

Benchmark: Linear -- clean tables with subtle row hover, inline status badges, keyboard-navigable, command-palette filtering.

---

## 3. Form Patterns

**Field Layout**

Good: `.stack stack-compact` for field groups (label + input + help text). Labels use `.text-sm font-medium`. Help text in `.text-sm` below the input. Required fields indicated with a subtle asterisk, not color alone.

Bad: Labels and inputs side-by-side on mobile. No help text. Required indicated only by red text (accessibility issue).

**Inline Validation**

Good: Error state via `data-state="error"` on the field wrapper. Error message appears below the field in `.text-sm` with error color from semantic token. Field border changes to error color. Validate on blur, not on every keystroke.

Bad: `alert()` for validation errors. Errors shown only at the top of the form after submission. No per-field indication.

**Multi-Step Forms**

Good: Step indicator showing current position and total steps. Each step in its own `.section`. Progress bar using `.progress-bar`. Back button always available. Data persists between steps.

Bad: No progress indication. Losing data when navigating back. All steps on one page with show/hide.

**Form Actions**

Good: Primary action as `.button button--accent`, secondary as `.button`. Destructive actions as `.button button--red` with confirmation via `popup-dialog`. Actions in `.cluster cluster-end` at the bottom of the form.

Bad: Multiple primary-styled buttons. No visual distinction between save and delete. Destructive actions without confirmation.

Benchmark: Stripe -- inline validation, clear field hierarchy, progressive disclosure, auto-save where possible.

---

## 4. Navigation Patterns

**Sidebar Navigation**

Good: `.sidebar` layout with nav in the aside. Active item via `data-state="active"`. Collapsible groups for sections with more than 5 items. Icons consistent in size and style. Mobile: sidebar collapses to hamburger menu.

Bad: Active state via `.active` or `.is-active` class. No collapse on mobile. Inconsistent icon sizes. Too many top-level items without grouping.

**Breadcrumbs**

Good: `.breadcrumbs` component for any page deeper than 2 levels. Current page is plain text (not a link). Separator is a subtle chevron. Truncate long breadcrumb chains with ellipsis for middle items.

Bad: No breadcrumbs on deep pages. Current page as a link (navigating to where you already are). Breadcrumbs as `Home > Page > Subpage` with `>` character.

**Active States**

Good: `data-state="active"` attribute on the nav item. Styled with left border or background highlight using semantic color token `--color-accent`. Clear visual distinction from hover state.

Bad: `.active` class. Background color from hardcoded hex. Active state identical to hover state.

Benchmark: Notion -- collapsible sidebar with drag-to-reorder, clear active indicators, smooth transitions between sections.

---

## 5. Feedback Patterns

**Toast Notifications**

Good: Appear at bottom-right or top-center. Auto-dismiss after 5 seconds for success, persistent for errors. Include undo action for destructive operations. Stack vertically when multiple. Animate in with subtle slide + fade.

Bad: `alert()` for notifications. No auto-dismiss. No undo. Notifications covering important content.

**Progress Indicators**

Good: `.progress-bar` for determinate progress (file uploads, multi-step processes). Skeleton loaders for content that's loading (not spinners). Spinners ONLY for actions where completion time is unknown and brief (submitting a form). `.stacked-bar` for multi-part progress.

Bad: Spinners for everything. No skeleton loaders. "Loading..." text. Blank page while data loads.

**Skeleton Loaders**

Good: Match the exact layout of the content being loaded. Use subtle pulse animation. Show the skeleton for lists, cards, text blocks, and images. Transition smoothly to real content.

Bad: A single generic spinner. Skeleton that doesn't match the actual content layout. Flash of skeleton then flash of content (no transition).

**Confirmation Dialogs**

Good: `popup-dialog` component for all destructive actions. Clear title stating what will happen. Body explains consequences. Confirm button uses `.button button--red` for destructive actions. Cancel is always available and visually secondary.

Bad: `confirm()` browser dialog. Vague "Are you sure?" without explaining consequences. Same button style for confirm and cancel.

Benchmark: Vercel -- elegant toast system with undo, smooth skeleton loaders, minimal but informative progress indicators.

---

## 6. Interaction Patterns

**Hover States**

Good: All interactive elements have a visible hover state. Transition with `150-200ms ease`. Cards lift slightly on hover (subtle shadow increase). Buttons darken or lighten. Links underline on hover.

Bad: No hover states. Instant state changes (no transition). Hover states only on some elements.

**Keyboard Navigation**

Good: All interactive elements reachable via Tab. Clear focus indicators (visible ring using `--color-accent`). Enter/Space activates buttons. Escape closes modals and dropdowns. Arrow keys navigate lists.

Bad: Focus indicators removed for aesthetics. Custom elements not keyboard-accessible. No escape-to-close on modals.

**Inline Editing**

Good: Click-to-edit with clear visual affordance (pencil icon or subtle border on hover). Edit mode uses the same layout position as display mode. Save on blur or Enter. Cancel on Escape. Optimistic update with error rollback.

Bad: Edit mode in a separate page or modal. No visual indication that a field is editable. Save button required (no keyboard shortcuts).

Benchmark: Linear -- extensive keyboard shortcuts, command palette for everything, smooth inline editing, optimistic updates.

---

## 7. Mobile and Responsive Patterns

**Responsive Layout**

Good: Container queries with `@md` and `@lg` suffixes (not media queries). `.grid` handles responsive columns automatically via `auto-fit`. Sidebar collapses to stacked layout on small containers. Touch targets minimum 44x44px.

Bad: `@media (min-width: 768px)` breakpoints. Fixed column counts that break on mobile. Tiny tap targets. Horizontal scrolling on content pages.

**Responsive Typography**

Good: Type scale uses `clamp()` for fluid sizing (built into `--text-*` tokens). Headings scale down gracefully on mobile. Reading measure stays within `--measure` (65ch) on wide screens.

Bad: Fixed `px` font sizes. Same heading size on mobile and desktop. Text running edge-to-edge with no measure constraint.

**Responsive Tables**

Good: Tables with horizontal scroll in a `.reel` on mobile. Or restructure to card layout at small sizes. Column priority -- hide least important columns first.

Bad: Table shrinks until text wraps and becomes unreadable. No scroll affordance. All columns shown at all sizes.

Benchmark: Apple HIG -- fluid responsive design, proper touch targets, adaptive layouts that feel native to each device size.

---

## 8. Common AI/Amateur Mistakes

These are the specific patterns that separate amateur UI from professional SaaS quality. Flag any of these as findings:

| Mistake | Fix (Live Wires) |
|---------|-----------------|
| Hardcoded `px`/`rem`/`em` spacing | Use `--line-*` tokens (`--line-1`, `--line-2`, etc.) |
| `.is-active`, `.active`, `.disabled` classes | Use `data-state="active"`, `data-state="disabled"` |
| `margin-top`, `padding-left` (physical properties) | Use logical properties: `margin-block-start`, `padding-inline-start` |
| Manual flexbox layout | Use `.cluster`, `.sidebar`, `.center` primitives |
| Separate `bg-grey-200` + `text-black` | Use `.scheme-grey-200` (bundles bg + fg for contrast) |
| `font-size: var(--text-2xl)` alone | Use full triplet: size + `--line-height-2xl` + `--tracking-2xl` |
| BEM `__` child selectors (`.card__title`) | Use CSS nesting: `.card { & .title { } }` |
| Inventing new class names | Check existing primitives and utilities first |
| `@media (min-width: 768px)` | Use container queries: `@container (min-width: 40rem)` or `@md` suffix |
| `!important` | Never. Cascade layers handle specificity. |
| Spinners for all loading states | Skeleton loaders for content, spinners only for brief unknown-duration actions |
| `alert()` or `confirm()` for feedback | Toast notifications, `popup-dialog` for confirmations |
| No empty states on lists | Every list needs an empty state with explanation and CTA |
| No loading states | Every data fetch needs a skeleton loader |
| No button hierarchy | One primary (`.button--accent`), rest secondary (`.button`) |
| Centered text in left-aligned layouts | Trust left-alignment. Center only for hero sections and CTAs. |
| Too many colors | Use the semantic color tokens. Limit accent usage. |
| Missing hover/focus transitions | All interactive elements need hover + focus states with 150-200ms transition |
| Inline styles | Check if a utility class exists first. Use tokens via custom properties. |
| Manual `padding` on sections | Use `.box` with variants (`box-tight`, `box-loose`) |
| Manual `margin-bottom` between elements | Use `.stack` (handles vertical spacing for all children) |
| `.text-muted` on every secondary element | Use sparingly. Most text inherits adequate contrast from its scheme. Reserve `text-muted` for genuinely de-emphasized metadata like footnotes or timestamps in dense views. Labels, help text, descriptions, and empty states should use default text color. |
| Full-width buttons (`.w-full`, `width: 100%`, block-level) | Buttons should be natural width. Full-width buttons are almost never correct -- they signal a missing layout decision. Use `.cluster` to group buttons. Exception: mobile CTA in a narrow column where tapping a wide target helps. |

---

## 9. AI Output Anti-Patterns (Design-Level)

Higher-level design decisions that signal AI generation, beyond the code-level mistakes in section 8. For the full 25-point scoreable checklist, see `${CLAUDE_PLUGIN_ROOT}/plugins/dm-review/skills/review/references/ai-slop-detector.md`. The quick-reference table below covers the most common tells with Live Wires fixes:

| AI Tell | Fix (Live Wires) |
|---------|-----------------|
| Three-equal-cards layout (no hierarchy) | Use `.grid` with `span` variation, `.sidebar` for primary/secondary |
| Centered hero + subheading + CTA | Left-aligned with asymmetric composition, or `.sidebar` |
| Side-stripe border on cards (`border-left: 3px+`) | Use `.scheme-*` for section differentiation |
| Identical section structure throughout | Vary `.section` density, break with editorial elements |
| Pure gray neutrals | Tint toward brand hue at low chroma (OKLCH) |
| Generic CTAs ("Get Started", "Learn More") | Specific action verbs: "View proposals," "Submit vote" |
