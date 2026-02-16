# Governance Workflows

State machines and workflows for Assembly governance.

## The Governance Chain

```
PROPOSAL → DECISION → RESOLUTION
              ↑
           VOTING
              ↑
         MEETING (optional)
```

### Core Entities

| Entity | Purpose |
|--------|---------|
| **Proposal** | Something to be decided on |
| **Decision** | The atomic unit capturing the vote |
| **Resolution** | Formal record of passed decisions |
| **Meeting** | Context where decisions happen |

---

## Proposal Workflow

### Status Flow

```
DRAFT → DISCUSSION → VOTING → PASSED/FAILED
  ↓         ↓           ↓
WITHDRAWN  DEFERRED   DEFERRED
```

### Status Values

| Status | Description | Actions Available |
|--------|-------------|-------------------|
| `draft` | Author working on it | Edit, Delete, Submit |
| `discussion` | Open for member input | Edit, Schedule, Withdraw |
| `voting` | Vote in progress | Cast Vote |
| `passed` | Approved | View Resolution |
| `failed` | Rejected | Archive |
| `deferred` | Postponed | Reschedule |
| `withdrawn` | Author withdrew | Archive |

### Handler Actions

```go
// Submit proposal (draft → discussion)
POST /governance/proposals/{id}/submit

// Schedule for meeting (discussion → voting at meeting)
POST /governance/proposals/{id}/schedule

// Start voting
POST /governance/proposals/{id}/start-voting

// Close voting (→ passed/failed)
POST /governance/proposals/{id}/close-voting

// Defer
POST /governance/proposals/{id}/defer

// Withdraw
POST /governance/proposals/{id}/withdraw
```

---

## Meeting Workflow

### Status Flow

```
DRAFT → SCHEDULED → IN_PROGRESS → COMPLETED
  ↓         ↓
CANCELLED CANCELLED
```

### Status Values

| Status | Description | Actions Available |
|--------|-------------|-------------------|
| `draft` | Being planned | Edit, Schedule, Delete |
| `scheduled` | Date set, notice sent | Edit, Start, Cancel |
| `in_progress` | Meeting happening | Record Attendance, Vote |
| `completed` | Meeting finished | View Minutes |
| `cancelled` | Meeting cancelled | Archive |

### Meeting Types

| Type | Quorum | Typical Decisions |
|------|--------|-------------------|
| `agm` | Per bylaws | Annual reports, elections |
| `special` | Per bylaws | Urgent matters |
| `board` | Majority of directors | Operational decisions |
| `committee` | Varies | Domain-specific |

### Quorum Calculation

```go
// Calculate quorum from attendance
func calculateQuorum(meetingID string) (required, present int, met bool)

// Quorum sources:
// - meeting.quorum_required (set at meeting creation)
// - Count of attendance WHERE type IN ('present', 'proxy')
```

---

## Decision Workflow

### Status Flow

```
PENDING → PASSED/FAILED
    ↓
DEFERRED
```

### Decision Types

| Type | Threshold | Use Case |
|------|-----------|----------|
| `ordinary` | >50% (simple majority) | Regular business |
| `special` | ≥66% (two-thirds) | Bylaw amendments |
| `unanimous` | 100% | Fundamental changes |
| `board` | >50% of directors | Board-level decisions |

### Threshold Calculation

```go
func calculateOutcome(votesFor, votesAgainst int, thresholdType string) string {
    totalVotes := votesFor + votesAgainst  // abstentions don't count
    percentFor := float64(votesFor) / float64(totalVotes) * 100

    thresholds := map[string]float64{
        "majority":       50,
        "two_thirds":     66.67,
        "three_quarters": 75,
        "unanimous":      100,
    }

    required := thresholds[thresholdType]

    if percentFor > required {  // strictly greater for majority
        return "passed"
    }
    return "failed"
}
```

### Voting Methods

| Method | Description | Use Case |
|--------|-------------|----------|
| `show_of_hands` | In-person, visible | Quick votes |
| `poll` | Secret ballot | Sensitive topics |
| `consent` | Written consent | Routine matters |
| `async` | Electronic vote | Between meetings |

---

## Resolution Workflow

### Status Flow

```
ACTIVE → SUPERSEDED/RESCINDED/EXPIRED
```

### Resolution Numbering

Format: `YYYY-NNN` or `YYYY-X-NNN`

| Type | Format | Example |
|------|--------|---------|
| Ordinary | `YYYY-NNN` | `2026-001` |
| Board | `YYYY-B-NNN` | `2026-B-007` |
| Special | `YYYY-S-NNN` | `2026-S-003` |

### Generation Logic

```go
func generateResolutionNumber(decisionType string) string {
    year := time.Now().Year()

    prefix := ""
    switch decisionType {
    case "board":
        prefix = "B-"
    case "special":
        prefix = "S-"
    }

    // Query max sequence for this year/type
    maxSeq := getMaxSequence(year, prefix)

    return fmt.Sprintf("%d-%s%03d", year, prefix, maxSeq+1)
}
```

---

## Attendance Workflow

### Attendance Types

| Type | Counts for Quorum | Can Vote |
|------|-------------------|----------|
| `present` | Yes | Yes |
| `proxy` | Yes | Via holder |
| `absent` | No | No |
| `excused` | No | No |
| `late` | Yes (after arrival) | Yes |

### Proxy Rules (BC Act s.43)

- Only if member >80km from meeting location
- Maximum 3 proxies per holder
- Proxy holder must be a member

```go
type ProxyValidation struct {
    DistanceRequirementKM int  // 80
    MaxProxiesPerHolder   int  // 3
    HolderMustBeMember    bool // true
}
```

---

## Implementation Checklist

### For Each Workflow Handler

- [ ] Validate current status allows transition
- [ ] Update status field
- [ ] Record timestamp
- [ ] Create audit log entry
- [ ] Trigger downstream actions (resolution creation, etc.)
- [ ] Return appropriate response

### Example Handler Structure

```go
func (h *Handlers) SubmitProposal(w http.ResponseWriter, r *http.Request) {
    id := chi.URLParam(r, "id")

    // 1. Fetch current state
    proposal, err := h.getProposal(id)
    if err != nil {
        h.error(w, http.StatusNotFound, "Proposal not found")
        return
    }

    // 2. Validate transition
    if proposal.Status != "draft" {
        h.error(w, http.StatusBadRequest, "Can only submit draft proposals")
        return
    }

    // 3. Update status
    _, err = h.db.Exec(`
        UPDATE proposals
        SET status = 'discussion', submitted_at = datetime('now')
        WHERE id = ?
    `, id)
    if err != nil {
        h.error(w, http.StatusInternalServerError, "Failed to submit")
        return
    }

    // 4. Redirect
    http.Redirect(w, r, "/governance/proposals/"+id, http.StatusSeeOther)
}
```

---

## Datastar Integration

### Live Voting UI

```templ
<div data-signals="{ voteChoice: '' }">
    <button type="button"
        data-class:button--accent="$voteChoice === 'for'"
        data-on:click="$voteChoice = 'for'">
        Vote For
    </button>
    <button type="button"
        data-class:button--accent="$voteChoice === 'against'"
        data-on:click="$voteChoice = 'against'">
        Vote Against
    </button>
    <button type="button"
        data-class:button--accent="$voteChoice === 'abstain'"
        data-on:click="$voteChoice = 'abstain'">
        Abstain
    </button>

    <button type="button"
        data-show="$voteChoice !== ''"
        data-on:click="@post('/governance/decisions/{id}/vote')">
        Submit Vote
    </button>
</div>
```

### Live Results

```templ
<div id="vote-results" data-on-interval="5000; @get('/sse/decisions/{id}/results')">
    // SSE endpoint pushes updated results
</div>
```

---

## See Also

- [assembly-governance-prototype-spec.md](../../../docs/assembly-governance-prototype-spec.md) - Full specification
- [assembly-requirements-checklist.md](../../../docs/assembly-requirements-checklist.md) - Requirements
