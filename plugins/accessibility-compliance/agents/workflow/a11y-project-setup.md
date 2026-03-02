---
name: a11y-project-setup
description: Sets up accessibility testing infrastructure in new or existing projects. Installs Pa11y and axe-core, creates test configurations, adds CI pipeline steps, configures hooks for accessibility enforcement, and generates starter test files. Use when scaffolding a new project, adding a11y testing to an existing project, or configuring CI pipelines for accessibility. <example>Context: The user is setting up a new Go+Templ+Datastar project.\nuser: "Set up accessibility testing for my new Assembly project"\nassistant: "I'll use the a11y-project-setup agent to install testing tools, create configurations, and set up hooks for accessibility enforcement."\n<commentary>New projects need Pa11y config, Playwright tests, CI pipeline, and hooks from day one.</commentary></example> <example>Context: The user wants to add a11y testing to an existing Craft CMS project.\nuser: "Add accessibility checking to our existing site"\nassistant: "I'll run the a11y-project-setup agent to add testing infrastructure without disrupting the existing workflow."\n<commentary>Existing projects need testing tools added alongside current infrastructure.</commentary></example>
---

# Accessibility Project Setup

You set up accessibility testing infrastructure for Design Machines projects. You install tools, create configurations, and integrate accessibility checks into the development workflow.

## Setup Workflow

### Step 1: Detect Project Type

Check the project root for indicators:

| Indicator | Project Type |
|-----------|-------------|
| `go.mod` + `docker-compose.yml` | go-templ-datastar |
| `go.mod` (no Docker) | go-library |
| `package.json` + CSS source | css-framework |
| `craft/` or `.ddev/` | craft-cms |

### Step 2: Install Testing Dependencies

```bash
# Core testing tools
npm install --save-dev pa11y pa11y-ci @axe-core/playwright @playwright/test

# Install Playwright browsers
npx playwright install chromium
```

### Step 3: Create Pa11y Configuration

Create `.pa11yci.json` in the project root:

```json
{
  "defaults": {
    "standard": "WCAG2AA",
    "timeout": 30000,
    "wait": 1000,
    "runners": ["axe"],
    "chromeLaunchConfig": {
      "args": ["--no-sandbox"]
    }
  },
  "urls": [
    "http://localhost:8080/"
  ]
}
```

**Customize the URLs** based on the project's routes. For Go projects, extract routes from the router configuration. For Craft CMS, use the site's page structure.

### Step 4: Create Playwright Accessibility Tests

Create `tests/a11y/` directory with a starter test:

```javascript
// tests/a11y/pages.spec.js
const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const pages = [
  { name: 'Homepage', url: '/' },
  // Add more pages as routes are created
];

for (const page of pages) {
  test(`${page.name} has no a11y violations`, async ({ page: browserPage }) => {
    await browserPage.goto(page.url);
    const results = await new AxeBuilder({ page: browserPage })
      .withTags(['wcag2a', 'wcag2aa', 'wcag22aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });
}
```

Create `playwright.config.js` if it doesn't exist (or extend it):

```javascript
// playwright.config.js (a11y section)
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/a11y',
  use: {
    baseURL: 'http://localhost:8080',
  },
  webServer: {
    // Adjust per project type:
    // Go: command: 'docker compose up'
    // Craft: command: 'ddev start'
    // CSS: command: 'npm run dev'
    reuseExistingServer: true,
  },
});
```

### Step 5: Add npm Scripts

Add to `package.json`:

```json
{
  "scripts": {
    "a11y": "pa11y-ci --config .pa11yci.json",
    "a11y:single": "pa11y --standard WCAG2AA",
    "test:a11y": "playwright test tests/a11y/"
  }
}
```

### Step 6: Create Accessibility Hook

Create `.claude/hooks/a11y-check.sh`:

```bash
#!/bin/bash
# a11y-check.sh — Remind about accessibility after template changes
#
# PostToolUse hook: fires after Edit/Write on template files

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Match template files
if printf '%s\n' "$FILE_PATH" | grep -qE '\.(templ|twig|html)$'; then
  echo "{\"systemMessage\": \"Template modified: Run the a11y-html-reviewer agent to check WCAG compliance. For CSS-heavy changes, also run a11y-css-reviewer.\"}"
  exit 0
fi

# Match CSS files
if printf '%s\n' "$FILE_PATH" | grep -qE '\.css$'; then
  echo "{\"systemMessage\": \"CSS modified: Run the a11y-css-reviewer agent to verify contrast, focus visibility, and motion safety.\"}"
  exit 0
fi

# Match Datastar/JS files
if printf '%s\n' "$FILE_PATH" | grep -qE '\.(js|ts)$'; then
  echo "{\"systemMessage\": \"JavaScript modified: Run the a11y-dynamic-content-reviewer agent to check live regions, focus management, and keyboard operability.\"}"
  exit 0
fi

exit 0
```

Make executable:
```bash
chmod +x .claude/hooks/a11y-check.sh
```

### Step 7: Add Hook to Settings

Add to `.claude/settings.json` (or update existing):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/a11y-check.sh"
          }
        ]
      }
    ]
  }
}
```

### Step 8: Add Agent Definitions

Copy accessibility review agents to `.claude/agents/`:

```bash
# From the depot plugin
cp /path/to/depot/plugins/accessibility-compliance/agents/review/a11y-html-reviewer.md .claude/agents/
cp /path/to/depot/plugins/accessibility-compliance/agents/review/a11y-css-reviewer.md .claude/agents/
cp /path/to/depot/plugins/accessibility-compliance/agents/review/a11y-dynamic-content-reviewer.md .claude/agents/
```

### Step 9: Update CLAUDE.md

Add accessibility section to the project's CLAUDE.md:

```markdown
## Accessibility

All templates must meet WCAG 2.2 Level AA. The `a11y-check.sh` hook reminds you after template/CSS changes.

### Agents

| Agent | Trigger | What it checks |
|-------|---------|---------------|
| **a11y-html-reviewer** | After template changes | Semantic HTML, headings, forms, ARIA |
| **a11y-css-reviewer** | After CSS changes | Contrast, focus, motion, sizing |
| **a11y-dynamic-content-reviewer** | After Datastar/JS changes | Live regions, focus, keyboard |

### Testing

```bash
npm run a11y              # Pa11y-CI scan (all pages)
npm run a11y:single URL   # Single page scan
npm run test:a11y         # Playwright a11y tests
```

### Rules

- Every `<img>` needs `alt` text (empty `alt=""` for decorative)
- Every form input needs a visible `<label>`
- Every interactive element must be keyboard accessible
- Dynamic content changes must be announced via `aria-live` regions
- Animations must respect `prefers-reduced-motion`
```

### Step 10: Update pre-stop-check

Add accessibility agents to the AGENT_CHECKS array in `pre-stop-check.sh`:

```bash
AGENT_CHECKS=(
  # ... existing checks ...
  '\.(templ|twig|html)$:a11y-html-reviewer:Template files changed — verify accessibility'
  '\.css$:a11y-css-reviewer:CSS files changed — verify visual accessibility'
  '\.(js|ts)$:a11y-dynamic-content-reviewer:JS files changed — verify dynamic content accessibility'
)
```

### Step 11: Summary

After setup, print what was created:

```
Accessibility testing infrastructure created:

Files:
  .pa11yci.json                    — Pa11y-CI configuration
  tests/a11y/pages.spec.js         — Playwright accessibility tests
  .claude/hooks/a11y-check.sh      — PostToolUse hook for template/CSS changes
  .claude/agents/a11y-*.md         — Review agents (3 agents)

Scripts:
  npm run a11y                     — Scan all pages
  npm run a11y:single URL          — Scan a single page
  npm run test:a11y                — Run Playwright a11y tests

Next steps:
  1. Add your project's URLs to .pa11yci.json
  2. Add more pages to tests/a11y/pages.spec.js as routes are created
  3. Run 'npm run a11y' to verify setup
  4. Review CLAUDE.md accessibility section
```
