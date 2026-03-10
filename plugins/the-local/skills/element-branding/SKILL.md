---
name: element-branding
description: Provides Element Web branding knowledge including custom CSS injection methodology, welcome page customization, auth page styling, service worker caching behaviour, and all visual override patterns for thelocal.chat. Use when editing custom.css, index.html, welcome/index.html, or element-config.json. Trigger for any mention of: Element Web appearance, auth page styling, logo replacement, welcome page, mx_AuthPage, mx_Login_submit, custom_css_url, welcomePageUrl, service worker, brand purple, or any visual change to thelocal.chat's Element Web interface. Also trigger when investigating CSS not applying, button styling issues, font overrides, or layout problems on the sign-in or welcome screens.
---

# The Local — Element Web Branding

Element Web runs at `thelocal.chat`, branded as "The Local". This skill documents the working CSS injection method, key gotchas, and all CSS class targets discovered through implementation.

## CSS Injection Architecture

**Working method** (Element Web v1.12):

Element's `custom_css_url` config field and `welcomeBackgroundUrl` are unreliable in v1.12. The working approach is:

1. A custom `assets/index.html` is mounted over `/app/index.html:ro` in Docker.
2. That file contains `<link rel="stylesheet" href="/assets/custom.css?v=N">` in `<head>`.
3. `custom.css` is served by Caddy from the host bind-mounted `assets/` directory.

**Key files**:
- `assets/index.html` — custom entry point, injects the CSS link tag
- `assets/custom.css` — all brand overrides (version-bumped on each deploy)
- `docker-compose.yml` — contains `- ./assets/index.html:/app/index.html:ro`

**Cache-busting**: Increment `?v=N` on the CSS link when deploying style changes so browsers bypass their cache.

## Welcome Page (welcomePageUrl)

**Config** in `element-config.json`:
```json
"welcomePageUrl": "welcome.html?v=2"
```

**How it works**: Element fetches `welcomePageUrl` and injects the HTML **inline** (not in an iframe) via `innerHTML` into `.mx_WelcomePage`. This means:
- `<style>` blocks apply globally to the parent thelocal.chat document
- `<script>` tags do NOT execute (innerHTML injection blocks scripts)

**Critical scoping rule**: Every CSS selector in `welcome/index.html` MUST be prefixed with a unique wrapper class (`.tlw`). Bare selectors (`body {}`, `h1 {}`, `p {}`, `a {}`) leak into Element's parent document and break the entire UI.

**Correct pattern**:
```css
.tlw .heading { font-size: 1.5rem; }   /* good — scoped */
h1 { font-size: 1.5rem; }              /* bad — leaks globally */
```

**SW cache bypass**: Use `welcome.html?v=2` (not just `welcome.html`) as the `welcomePageUrl`. The service worker precaches `welcome.html` at build time — any different URL won't be in the precache manifest and will be fetched fresh.

## Auth Page CSS Targets

Discovered class targets for `/#/login` and `/#/register`:

```css
/* Full-page wrapper — background must use !important (Element sets it inline via JS) */
.mx_AuthPage { background: #220D46 !important; }

/* Frosted card overlay — filter and background set inline; override with !important */
.mx_AuthPage_modalBlur { background: rgba(249, 245, 240, 0.96) !important; filter: none !important; }

/* Auth modal card — rounded corners */
.mx_AuthPage_modal { border-radius: 24px !important; overflow: hidden !important; }

/* Right panel content area */
.mx_AuthPage_modalContent { background: #F9F5F0 !important; }

/* Left panel — Element logo image */
.mx_AuthHeaderLogo img { display: none !important; }

/* Left panel — replace with The Local logo */
.mx_AuthHeaderLogo {
    background-image: url('/assets/the-local-logo.png');
    background-size: 140px auto;
    background-repeat: no-repeat;
    background-position: center 36px;
}

/* Footer links (Blog, Matrix, GitHub) */
.mx_AuthPage .mx_AuthFooter { display: none !important; }

/* Language dropdown */
.mx_AuthBody_language { display: none !important; }

/* Secondary links color */
.mx_AuthBody a,
.mx_Login_forgot,
.mx_AuthBody .mx_AccessibleButton_kind_link { color: #220D46 !important; }
```

## Submit Button Override (Critical)

Element's `.mx_DialogButton` mixin is applied to `.mx_Login_submit` and `.mx_Register_submit`. It sets:
- `height: 32px` — fixed height that compresses the button
- `font: var(--cpd-font-body-md-regular)` — a CSS `font` shorthand that resets ALL font properties in one declaration, overriding individually-set `font-size`, `font-weight`, `font-family`

**The fix — must override in this exact order**:
```css
.mx_Login_submit,
.mx_Register_submit {
    -webkit-appearance: none !important;  /* clear WebKit native button chrome */
    appearance: none !important;
    font: unset !important;               /* neutralize the cpd font shorthand first */
    font-family: inherit !important;      /* then re-apply individually */
    font-size: 14px !important;
    font-weight: 700 !important;
    line-height: 1.5 !important;
    height: auto !important;             /* override fixed 32px height */
    min-height: 0 !important;
    /* ... rest of button styles */
}
```

**Why `font: unset !important` first**: CSS `font` shorthand resets all font sub-properties. If you only set `font-size: 14px !important`, the `font` shorthand still wins for other properties. `font: unset` neutralizes the shorthand, then individual declarations take effect.

## Welcome Page Structure

`welcome/index.html` — injected inline into `.mx_WelcomePage`:

```html
<div class="tlw">
    <img src="/assets/the-local-logo.png" alt="The Local" class="logo" />
    <div class="main">
        <div class="eyebrow">Federated · Self-hosted · Encrypted</div>
        <div class="heading">Communications for the workplace democracy movement.</div>
        <div class="divider"></div>
        <p class="desc">...</p>
        <p class="access">Membership by invitation</p>
        <div class="button-row">
            <a href="/#/login" target="_top" class="btn-primary">Sign in</a>
            <a href="/#/register" target="_top" class="btn-outline">Create account</a>
        </div>
    </div>
    <div class="footer">
        <a href="https://designmachines.studio">Design Machines</a>
    </div>
</div>
```

**Note**: `target="_top"` on links is required because Element intercepts navigation — `_top` breaks out of any parent context.

## Brand Palette

| Token | Hex | Use |
|-------|-----|-----|
| Brand purple | `#220D46` | Backgrounds, text, primary button |
| Purple hover | `#2d1060` | Button hover states |
| Red accent | `#ed1d26` | Eyebrow text, dividers |
| Warm white | `#F9F5F0` | Card backgrounds, primary text on dark |
| Muted purple | `#5a4a7a` | Body copy |
| Disabled | `#8a8299` | Metadata, access labels |
| Ghost | `#c0bac8` | Footer text |

## Service Worker Behavior

Element Web registers a service worker that aggressively precaches assets from the build manifest. This causes stale versions to persist for returning visitors.

**Do NOT add a `<script>` tag to `assets/index.html` to unregister the SW**. This approach breaks Element's JavaScript bundle loading in some browsers (tested: Vivaldi Private mode — only 6 network requests instead of ~47, Element never initializes).

**Safe workarounds**:
- Version-bump `?v=N` on the CSS href (bypasses browser cache for the CSS file itself)
- Use `welcome.html?v=2` as `welcomePageUrl` (bypasses SW precache for welcome content)
- Users with stale SW: DevTools → Application → Service Workers → Unregister, then reload

## Element Config (element-config.json)

```json
{
  "default_server_config": {
    "m.homeserver": {
      "base_url": "https://matrix.thelocal.chat",
      "server_name": "thelocal.chat"
    }
  },
  "brand": "The Local",
  "welcomePageUrl": "welcome.html?v=2",
  "disable_custom_urls": true,
  "disable_guests": true,
  "disable_3pid_login": true,
  "default_theme": "light"
}
```
