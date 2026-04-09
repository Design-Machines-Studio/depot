# Design Context Questionnaire

Before providing any design advice, critique, or direction, establish context. This is non-negotiable.

- Chimero: Why before How
- Gerstner: criteria before creation
- Spiekermann: what is being said, to whom, in what medium, what response is desired

---

## Minimum Required Context

If ANY of these are unknown and this is not a DM property, ask before proceeding:

1. **Purpose** -- What must this design accomplish? Not "look nice" -- specific: "convert visitors to members," "help board members vote on proposals," "explain the service offering."
2. **Audience** -- Who will see this? Technical sophistication, design literacy, cultural context, accessibility needs.
3. **Medium** -- Where will this live? Web (responsive range), print (size, paper), screen (display context), physical environment (signage, packaging).

## Extended Context (ask when relevant)

4. **Brand** -- Is there an existing identity? Color palette? Typeface? Style guide? If yes, the design must extend the system, not start fresh.
5. **Competitive landscape** -- What do others in this space look like? Draplin's competitive contrast: know what everyone else does, then do something intentional.
6. **Constraints** -- Budget, timeline, technical stack, existing component library, performance budget, accessibility level (WCAG AA/AAA).
7. **Personality** -- What adjectives describe the desired tone? Map along axes: warm/cold, formal/casual, bold/restrained, playful/serious.
8. **Content type** -- Long-form editorial? Data-heavy dashboard? Marketing landing page? Application UI? Governance interface? This determines everything from measure to density.

## For DM Property Work

When working on any Design Machines property (Assembly, Live Wires, Design Machines, The Local), context is pre-established. Skip the questionnaire and proceed directly to domain advice.

- **Typeface:** GT Standard (variable, Grilli Type) -- no secondary typefaces
- **Framework:** Live Wires CSS (CUBE methodology, baseline rhythm, layout primitives)
- **Tech stack:** Go + Templ + Datastar (Assembly), Craft CMS + Twig (marketing sites)
- **Brand palette:** Purple-800, Gold-400, Red-500, scheme classes for differentiation
- **Personality:** Swiss precision, editorial warmth, cooperative democracy, bold but disciplined
- **Audience:** Worker cooperative members (Assembly), design/tech community (DM), local community (The Local)
- **Accessibility:** WCAG AA minimum, keyboard-navigable, screen-reader compatible

## Integration

The **design-advisor** agent must check this questionnaire before providing advice. If minimum context is missing and the project is not a DM property, ask -- never advise blind.

The **design-critic** agent evaluates work against established criteria. Context helps the critic understand intent before judging execution. A centered hero might be wrong for a governance app but right for a brand marketing page.
