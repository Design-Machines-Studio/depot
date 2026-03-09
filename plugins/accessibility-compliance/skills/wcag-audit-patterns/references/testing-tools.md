# Accessibility Testing Tools

Configuration guides and CI integration for automated accessibility testing.

## Contents
- [Tool Comparison](#tool-comparison) (line 17) -- Feature matrix of a11y testing tools
- [axe-core (Recommended Engine)](#axe-core-recommended-engine) (line 31) -- Playwright integration and rule configuration
- [Pa11y](#pa11y) (line 112) -- CLI scanning and CI configuration
- [Lighthouse](#lighthouse) (line 178) -- Broad audit CLI and limitations
- [CI Pipeline Integration](#ci-pipeline-integration) (line 195) -- GitHub Actions for Go and Craft stacks
- [Browser DevTools](#browser-devtools) (line 284) -- Chrome and Firefox accessibility panels
- [Manual Testing Tools](#manual-testing-tools) (line 302) -- Contrast checkers, extensions, and bookmarklets
- [Reporting Templates](#reporting-templates) (line 337) -- Pa11y and Playwright report output

---

## Tool Comparison

| Tool | Type | Best for | WCAG 2.2 | CI-ready |
|------|------|----------|----------|----------|
| **axe-core** | Library | Integrating into test suites | Yes | Yes |
| **Pa11y** | CLI | Quick page scans | Yes | Yes |
| **Pa11y-CI** | CLI | Multi-page scanning | Yes | Yes |
| **Lighthouse** | CLI/Browser | Broad audits (perf + a11y) | Partial | Yes |
| **Playwright + axe** | Framework | Test suite integration | Yes | Yes |
| **WAVE** | Browser ext. | Manual review | Partial | No |
| **axe DevTools** | Browser ext. | Deep manual analysis | Yes | No |

---

## axe-core (Recommended Engine)

axe-core is the industry standard engine. Used by Pa11y (optionally), Lighthouse (internally), and directly via Playwright.

### Install

```bash
npm install --save-dev @axe-core/playwright
```

### Playwright Integration

```javascript
// tests/a11y/page.spec.js
const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

test.describe('Accessibility', () => {
  test('homepage has no violations', async ({ page }) => {
    await page.goto('/');
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag22aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('login form has no violations', async ({ page }) => {
    await page.goto('/login');
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag22aa'])
      .include('#login-form')
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('dashboard after login', async ({ page }) => {
    // Login first
    await page.goto('/login');
    await page.fill('#email', 'test@example.com');
    await page.fill('#password', 'testpassword');
    await page.click('button[type="submit"]');
    await page.waitForURL('/dashboard');

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag22aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });
});
```

### Scoping

```javascript
// Only test a specific region
.include('#main-content')

// Exclude known third-party widgets
.exclude('.third-party-embed')

// Disable specific rules
.disableRules(['color-contrast']) // only if you have a documented exception
```

### Custom Rule Tags

| Tag | Description |
|-----|-------------|
| `wcag2a` | WCAG 2.0 Level A |
| `wcag2aa` | WCAG 2.0 Level AA |
| `wcag21a` | WCAG 2.1 Level A (includes 2.0) |
| `wcag21aa` | WCAG 2.1 Level AA |
| `wcag22aa` | WCAG 2.2 Level AA |
| `best-practice` | Best practices beyond WCAG |
| `section508` | Section 508 rules |

---

## Pa11y

### Install

```bash
npm install --save-dev pa11y pa11y-ci
```

### Single Page Scan

```bash
npx pa11y http://localhost:8080/ --standard WCAG2AA --reporter cli
```

### Pa11y-CI Configuration

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
    "http://localhost:8080/",
    "http://localhost:8080/login",
    "http://localhost:8080/dashboard",
    {
      "url": "http://localhost:8080/members",
      "actions": [
        "wait for element #member-list to be visible"
      ]
    }
  ]
}
```

### Run

```bash
npx pa11y-ci --config .pa11yci.json
```

### Actions for Dynamic Content

Pa11y supports actions to interact with pages before scanning:

```json
{
  "url": "http://localhost:8080/proposals",
  "actions": [
    "click element #tab-active",
    "wait for element #active-proposals to be visible",
    "screen capture screenshots/proposals-active.png"
  ]
}
```

---

## Lighthouse

### CLI

```bash
npx lighthouse http://localhost:8080/ \
  --only-categories=accessibility \
  --output=json \
  --output-path=./lighthouse-report.json
```

### Limitations

Lighthouse uses axe-core internally but runs fewer rules than a direct axe integration. It's best for broad audits; use axe-core directly for WCAG 2.2 compliance testing.

---

## CI Pipeline Integration

### GitHub Actions

```yaml
# .github/workflows/a11y.yml
name: Accessibility Checks

on:
  pull_request:
    paths:
      - '**/*.templ'
      - '**/*.twig'
      - '**/*.html'
      - '**/*.css'
      - '**/*.go'

jobs:
  a11y:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Install dependencies
        run: npm ci

      - name: Start application
        run: docker compose up -d
        # Adjust for your stack

      - name: Wait for app
        run: npx wait-on http://localhost:8080 --timeout 30000

      - name: Run Pa11y-CI
        run: npx pa11y-ci --config .pa11yci.json

      - name: Run Playwright a11y tests
        run: npx playwright test tests/a11y/
```

### Go Projects (Docker-based)

For Assembly-style projects, the CI pipeline should:

1. Build and start the Docker containers
2. Wait for the app to be healthy
3. Run Pa11y-CI against the running app
4. Run Playwright accessibility tests
5. Tear down containers

```yaml
      - name: Build and start
        run: docker compose up -d --build

      - name: Wait for healthy
        run: |
          for i in $(seq 1 30); do
            curl -sf http://localhost:8080/health && break
            sleep 1
          done

      - name: Accessibility scan
        run: npx pa11y-ci

      - name: Teardown
        if: always()
        run: docker compose down
```

### Craft CMS Projects (DDEV)

```yaml
      - name: Start DDEV
        run: ddev start

      - name: Import database
        run: ddev import-db --file=tests/fixtures/db.sql.gz

      - name: Accessibility scan
        run: npx pa11y-ci --config .pa11yci.json
```

---

## Browser DevTools

### Chrome DevTools

- **Lighthouse tab** — quick accessibility audit
- **Elements panel** — Accessibility pane shows ARIA tree, computed name/role
- **Rendering tab** — emulate vision deficiencies (protanopia, deuteranopia, etc.)
- **Rendering tab** — emulate `prefers-reduced-motion`, `forced-colors`
- **CSS Overview** — shows contrast issues across the page

### Firefox DevTools

- **Accessibility panel** — full accessibility tree with issue highlighting
- **Contrast checker** — inline in the color picker
- **Tab order overlay** — visualizes keyboard navigation order

---

## Manual Testing Tools

### Contrast Checkers

| Tool | URL | Notes |
|------|-----|-------|
| WebAIM Contrast Checker | https://webaim.org/resources/contrastchecker/ | Simple two-color checker |
| Accessible Colors | https://accessible-colors.com/ | Suggests closest accessible color |
| Colour Contrast Analyser (CCA) | Download from TPGi | Desktop app, eyedropper tool |

### Browser Extensions

| Extension | Browser | Purpose |
|-----------|---------|---------|
| axe DevTools | Chrome, Firefox | Deep page analysis |
| WAVE | Chrome, Firefox | Visual overlay of issues |
| Accessibility Insights | Chrome | Microsoft's testing tool |
| HeadingsMap | Chrome, Firefox | Heading hierarchy visualization |

### Bookmarklets

**Text spacing test** (WCAG 1.4.12):

```javascript
javascript:void(function(){var s=document.createElement('style');s.textContent='*{line-height:1.5!important;letter-spacing:0.12em!important;word-spacing:0.16em!important}p{margin-bottom:2em!important}';document.head.appendChild(s)})()
```

**Show focus order:**

```javascript
javascript:void(function(){var i=0;document.querySelectorAll('a,button,input,select,textarea,[tabindex]').forEach(function(e){if(e.tabIndex>=0){i++;var l=document.createElement('span');l.style.cssText='position:absolute;background:red;color:white;font-size:12px;padding:2px 4px;z-index:99999';l.textContent=i;e.style.position='relative';e.appendChild(l)}})})()
```

---

## Reporting Templates

### Pa11y JSON Output

```bash
npx pa11y http://localhost:8080/ --reporter json > a11y-report.json
```

### Custom HTML Report

```bash
npx pa11y http://localhost:8080/ --reporter html > a11y-report.html
```

### Playwright Report

Configure in `playwright.config.js`:

```javascript
reporter: [
  ['html', { outputFolder: 'a11y-report' }],
  ['json', { outputFile: 'a11y-results.json' }]
]
```
