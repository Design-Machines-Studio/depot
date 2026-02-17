# Components Reference

Templ components for Assembly. Located in `backend/internal/components/`.

## Display Components

### Avatar

Member avatar with initials fallback.

```templ
@components.Avatar(name, size)
// size: "small", "medium", "large"

// Example
@components.Avatar("Jane Smith", "medium")
// Renders: <div class="avatar avatar--medium">JS</div>
```

### Badge

General-purpose badge with variants.

```templ
@components.Badge(text, variant)
// variant: "general", "special", "board", "ordinary", or custom

// Example
@components.Badge("Special", "special")
```

### StatusBadge

Pre-styled status indicator.

```templ
@components.StatusBadge(status)
// status: "active", "pending", "passed", "failed", "draft", "voting", etc.

// Example
@components.StatusBadge("active")
```

### StatCard

Dashboard statistic card with trend indicator.

```templ
@components.StatCard(components.StatCardProps{
    Title:       "Total Members",
    Value:       "24",
    Change:      "+2",
    ChangeLabel: "vs last quarter",
    Trend:       "up",  // "up", "down", "neutral"
})
```

### InfoCard

Information card with icon and description.

```templ
@components.InfoCard(components.InfoCardProps{
    Title:       "Upcoming AGM",
    Description: "April 15, 2026",
    Icon:        "calendar",
    Href:        "/governance/meetings/agm-2026",
})
```

### ActivityCard

Activity/timeline card.

```templ
@components.ActivityCard(components.ActivityCardProps{
    Title:     "New Proposal Submitted",
    Timestamp: "2 hours ago",
    Icon:      "document",
    Href:      "/governance/proposals/prop-001",
})
```

### ProgressBar

Progress indicator.

```templ
@components.ProgressBar(components.ProgressBarProps{
    Value:   75,
    Max:     100,
    Label:   "Budget Used",
    Variant: "default",  // "default", "success", "warning", "danger"
})
```

## Navigation Components

### ButtonLink

Link styled as button.

```templ
@components.ButtonLink(href, text, variant)
// variant: "", "accent", "danger"

// Examples
@components.ButtonLink("/members/new", "Add Member", "accent")
@components.ButtonLink("/back", "Cancel", "")
```

### InfoPopup

Modal popup trigger with information.

```templ
@components.InfoPopup(title, body)

// Example
@components.InfoPopup("What is quorum?", "The minimum number of members...")
```

## Form Components

### FormField

Complete form field with label, input, and error handling.

```templ
@components.FormField(components.FormFieldProps{
    Name:        "title",
    Label:       "Proposal Title",
    Type:        "text",  // "text", "email", "date", "number", "tel", "url"
    Placeholder: "Enter title...",
    Value:       "",
    Required:    true,
    Hint:        "Maximum 100 characters",
    Error:       "",
})
```

### TextArea

Multi-line text input.

```templ
@components.TextArea(components.TextAreaProps{
    Name:        "description",
    Label:       "Description",
    Rows:        5,
    Value:       "",
    Required:    false,
    Placeholder: "Enter description...",
})
```

### Select

Dropdown select.

```templ
@components.Select(components.SelectProps{
    Name:     "status",
    Label:    "Status",
    Options:  []components.SelectOption{
        {Value: "draft", Label: "Draft"},
        {Value: "active", Label: "Active"},
    },
    Selected: "draft",
    Required: true,
})
```

### Checkbox

Checkbox input.

```templ
@components.Checkbox(components.CheckboxProps{
    Name:    "agree",
    Label:   "I agree to the terms",
    Checked: false,
})
```

### Checklist

Group of checkboxes.

```templ
@components.Checklist(components.ChecklistProps{
    Name:  "attendees",
    Label: "Select Attendees",
    Items: []components.ChecklistItem{
        {Value: "member-1", Label: "Jane Smith", Checked: true},
        {Value: "member-2", Label: "John Doe", Checked: false},
    },
})
```

## Utility Components

### Loader

Loading indicator.

```templ
@components.Loader()
```

## Helper Functions

Located in `backend/internal/components/helpers.go`:

### Initials

Extract initials from a name.

```go
components.Initials("Jane Smith")  // "JS"
components.Initials("Alice Bob Chen")  // "AC"
```

### DateShort

Format date for display.

```go
components.DateShort(timeValue)  // "Jan 15, 2026"
```

### DateLong

Format date with time.

```go
components.DateLong(timeValue)  // "January 15, 2026 at 2:30 PM"
```

### FormatCurrency

Format number as currency.

```go
components.FormatCurrency(1500.50)  // "$1,500.50"
```

### Pluralize

Pluralize a word based on count.

```go
components.Pluralize(1, "member")  // "1 member"
components.Pluralize(5, "member")  // "5 members"
```

## Creating New Components

1. **Check if existing component can be extended**
2. **Create in `backend/internal/components/`**
3. **Follow the pattern:**

```templ
// component_name.templ
package components

type ComponentNameProps struct {
    // Required fields first
    Title    string
    // Optional fields with defaults
    Variant  string
}

templ ComponentName(props ComponentNameProps) {
    // Apply defaults
    if props.Variant == "" {
        props.Variant = "default"
    }

    <div class={ "component", "component--" + props.Variant }>
        { props.Title }
    </div>
}
```

4. **Generate and test:**

```bash
docker compose exec app templ generate
docker compose exec app go build ./cmd/api
```

## Usage in Templates

Import components in your templ file:

```templ
package mypage

import (
    "github.com/design-machines/assembly/internal/components"
)

templ MyPage() {
    @components.Avatar("Jane Smith", "medium")
    @components.StatusBadge("active")
    @components.ButtonLink("/edit", "Edit", "accent")
}
```
