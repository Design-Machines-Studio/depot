# Severity mappings for depot-native agents

Loaded only when the selected roster includes an agent from another depot
plugin (accessibility-compliance, live-wires, ghostwriter, or council). A
roster of dm-review agents alone never loads this file.

### Depot-Native Agents (from other plugins)

| Agent | Plugin | Critical/P1 | Serious/P2 | Moderate/P3 |
|-------|--------|------------|------------|-------------|
| **a11y-html-reviewer** | accessibility-compliance | Missing form labels, keyboard traps, no alt on functional images | Broken heading hierarchy, missing landmarks, generic link text | Missing aria-describedby, suboptimal ARIA |
| **a11y-css-reviewer** | accessibility-compliance | `outline: none` without replacement, failing contrast on primary text | Animations without motion check, reflow broken at 320px | Low contrast on secondary text, missing forced-colors |
| **a11y-dynamic-content-reviewer** | accessibility-compliance | Click handlers on non-interactive elements, no live regions for state changes | Focus lost after morph, loading states silent | ARIA states not synced, suboptimal focus target |
| **css-reviewer** | live-wires | -- (errors) | Cascade layer violations, class invention, naming rule breaks | Observable token or responsive defect with a bounded repair; alternative patterns alone are discarded |
| **voice-editor** | ghostwriter | -- | Spine failure (no point of view), AI pattern detected | Rhythm issues, minor register drift |
| **governance-domain** | council | Legal compliance failure (wrong voting threshold) | Architecture violation (fixture boundaries) | Observable terminology or values mismatch against approved policy; recommendations alone are discarded |

---
