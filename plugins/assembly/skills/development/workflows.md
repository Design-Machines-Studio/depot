# Governance Workflows

State machines and workflows for Assembly governance.

## The Governance Chain

```
PROPOSAL -> DECISION -> RESOLUTION
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
DRAFT -> DISCUSSION -> VOTING -> PASSED/FAILED
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
// Submit proposal (draft -> discussion)
POST /governance/proposals/{id}/submit

// Schedule for meeting (discussion -> voting at meeting)
POST /governance/proposals/{id}/schedule

// Start voting
POST /governance/proposals/{id}/start-voting

// Close voting (-> passed/failed)
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
DRAFT -> SCHEDULED -> IN_PROGRESS -> COMPLETED
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

### Quorum Not Met (Adjourned Meeting Rule)

Per the BC Act: if quorum is not achieved within 30 minutes of the scheduled start time, the meeting adjourns for 1 week. At the adjourned meeting, those present constitute quorum regardless of number.

---

## Decision Workflow

### Status Flow

```
PENDING -> PASSED/FAILED
    ↓
DEFERRED
```

### Decision Types

| Type | Threshold | Use Case |
|------|-----------|----------|
| `ordinary` | >50% (50% + 1) | Regular business |
| `special` | ≥2/3 of votes cast | Bylaw amendments |
| `unanimous` | 100% | Fundamental changes |
| `board` | >50% of directors | Board-level decisions |

### Threshold Calculation

Uses integer arithmetic to avoid floating-point rounding errors at small meeting sizes.

```go
func calculateOutcome(votesFor, votesAgainst int, thresholdType string) string {
    totalVotes := votesFor + votesAgainst  // abstentions don't count
    if totalVotes == 0 {
        return "failed"
    }

    switch thresholdType {
    case "majority":
        // 50% + 1 of votes cast (strictly greater than half)
        if votesFor*2 > totalVotes {
            return "passed"
        }
    case "two_thirds":
        // ≥ 2/3 of votes cast (BC Act special resolution)
        if votesFor*3 >= totalVotes*2 {
            return "passed"
        }
    case "three_quarters":
        // ≥ 3/4 of votes cast
        if votesFor*4 >= totalVotes*3 {
            return "passed"
        }
    case "unanimous":
        if votesFor == totalVotes {
            return "passed"
        }
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
ACTIVE -> SUPERSEDED/RESCINDED/EXPIRED
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

- [ ] Consult the development skill's Mutation Applicability Matrix and name why each selected control applies
- [ ] Authorize the concrete action/resource before a protected user or operator write
- [ ] Validate external input and current status for a domain transition
- [ ] Use a transaction only when atomic multi-step work, race-sensitive allocation, or a cross-read/write invariant requires it
- [ ] Record an audit entry only for a named high-consequence category or existing audit contract
- [ ] Trigger downstream actions or publish an event only for a current behavior, consumer, projection, or contract; publish required events after commit
- [ ] Notify through SSE only when connected clients currently need real-time notice
- [ ] Return the appropriate response and proportionally test the selected controls and important failure path

### Example Handler Structure

```go
func (h *Handlers) SubmitProposal(w http.ResponseWriter, r *http.Request) {
    id := chi.URLParam(r, "id")
    actor := auth.ContextMember(r.Context())
    if actor == nil {
        h.error(w, http.StatusForbidden, "Not authorized")
        return
    }

    if err := h.proposals.Submit(r.Context(), actor.ID, id); err != nil {
        h.writeProposalError(w, err) // maps denied/invalid/not-found/storage safely
        return
    }
    http.Redirect(w, r, "/governance/proposals/"+id, http.StatusSeeOther)
}

func (s *ProposalService) Submit(ctx context.Context, actorID, id string) error {
    proposal, err := s.getProposal(ctx, id)
    if err != nil {
        return err
    }
    if err := s.auth.Authorize(ctx, actorID, "proposal.submit", Resource{
        ID: proposal.ID, AuthorID: proposal.ProposedBy, Status: proposal.Status,
    }); err != nil {
        return err
    }
    if proposal.Status != "draft" {
        return ErrInvalidProposalTransition
    }
    _, err = s.db.ExecContext(ctx, `
        UPDATE $TABLE
        SET status = 'discussion', submitted_at = datetime('now')
        WHERE id = ?
    `, id)
    return err
}
```

This protected domain transition uses a service because authorization and a
status invariant belong to the domain boundary. The single SQL statement is
already atomic. Add audit, event, or SSE behavior only when the matrix identifies
a current obligation; publish any required event after the write commits.

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
