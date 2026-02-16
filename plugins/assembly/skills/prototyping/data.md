# Data Reference

Database schema, DTOs, and query patterns for Assembly.

## Database Location

SQLite database: `backend/data/coop.db`

Migrations: `backend/migrations/`

## Core Tables

### members

```sql
CREATE TABLE members (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    preferred_name TEXT,
    status TEXT DEFAULT 'active',  -- 'active', 'candidate', 'withdrawn', 'terminated'
    joined_at TEXT,
    departed_at TEXT,
    departure_reason TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
```

### member_roles

```sql
CREATE TABLE member_roles (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL REFERENCES members(id),
    role_name TEXT NOT NULL,  -- 'president', 'secretary', 'treasurer', 'director'
    display_name TEXT,
    description TEXT,
    is_board_role INTEGER DEFAULT 0,
    started_at TEXT,
    ended_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_member_roles_member ON member_roles(member_id);
```

### proposals

```sql
CREATE TABLE proposals (
    id TEXT PRIMARY KEY,
    proposal_number TEXT,
    title TEXT NOT NULL,
    summary TEXT,
    body TEXT,
    status TEXT DEFAULT 'draft',  -- 'draft', 'discussion', 'voting', 'passed', 'failed', 'deferred', 'withdrawn'
    proposal_type_id TEXT REFERENCES proposal_types(id),
    proposed_by TEXT REFERENCES members(id),
    created_at TEXT DEFAULT (datetime('now')),
    submitted_at TEXT,
    updated_at TEXT DEFAULT (datetime('now')),
    decision_id TEXT REFERENCES decisions(id)
);
```

### meetings

```sql
CREATE TABLE meetings (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    meeting_type TEXT NOT NULL,  -- 'agm', 'special', 'board', 'committee'
    scheduled_at TEXT,
    location TEXT,
    status TEXT DEFAULT 'draft',  -- 'draft', 'scheduled', 'in_progress', 'completed', 'cancelled'
    quorum_required INTEGER,
    quorum_present INTEGER,
    quorum_met INTEGER,
    called_to_order_at TEXT,
    adjourned_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
```

### meeting_attendance

```sql
CREATE TABLE meeting_attendance (
    id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL REFERENCES meetings(id),
    member_id TEXT NOT NULL REFERENCES members(id),
    attendance_type TEXT DEFAULT 'absent',  -- 'present', 'absent', 'proxy', 'excused', 'late'
    role_at_time TEXT,  -- 'Chair', 'Secretary', etc.
    proxy_holder_id TEXT REFERENCES members(id),
    arrived_at TEXT,
    left_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_meeting_attendance_meeting ON meeting_attendance(meeting_id);
CREATE INDEX idx_meeting_attendance_member ON meeting_attendance(member_id);
```

### decisions

```sql
CREATE TABLE decisions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT,
    decision_type TEXT NOT NULL,  -- 'ordinary', 'special', 'board'
    created_at TEXT DEFAULT (datetime('now')),
    decided_at TEXT,
    effective_date TEXT,
    meeting_id TEXT REFERENCES meetings(id),
    proposed_by TEXT REFERENCES members(id),
    voting_method TEXT,  -- 'show_of_hands', 'poll', 'consent', 'async'
    outcome TEXT DEFAULT 'pending',  -- 'pending', 'passed', 'failed', 'deferred'
    votes_for INTEGER DEFAULT 0,
    votes_against INTEGER DEFAULT 0,
    votes_abstain INTEGER DEFAULT 0,
    quorum_required INTEGER,
    quorum_present INTEGER,
    threshold_type TEXT,  -- 'majority', 'two_thirds', 'unanimous'
    threshold_met INTEGER,
    resolution_number TEXT,
    resolution_text TEXT,
    proposal_id TEXT REFERENCES proposals(id),
    resolution_id TEXT REFERENCES resolutions(id),
    notes TEXT
);

CREATE INDEX idx_decisions_meeting ON decisions(meeting_id);
CREATE INDEX idx_decisions_outcome ON decisions(outcome);
```

### resolutions

```sql
CREATE TABLE resolutions (
    id TEXT PRIMARY KEY,
    resolution_number TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    resolution_text TEXT,
    resolution_type TEXT,  -- 'general', 'special', 'board'
    status TEXT DEFAULT 'active',  -- 'active', 'superseded', 'rescinded'
    passed_at TEXT,
    effective_date TEXT,
    meeting_id TEXT REFERENCES meetings(id),
    decision_id TEXT REFERENCES decisions(id),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_resolutions_meeting ON resolutions(meeting_id);
```

---

## Administration Tables (Planned)

See [docs/adr-001-administration-architecture.md](../../../docs/adr-001-administration-architecture.md) for full details.

### modules

```sql
CREATE TABLE modules (
    id TEXT PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,  -- 'governance', 'discussions', etc.
    name TEXT NOT NULL,
    description TEXT,
    enabled INTEGER DEFAULT 0,
    config TEXT,  -- JSON for module-specific settings
    sort_order INTEGER DEFAULT 0
);
```

### groups

```sql
CREATE TABLE groups (
    id TEXT PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    is_system INTEGER DEFAULT 0,  -- Can't delete members, board, etc.
    created_at TEXT DEFAULT (datetime('now'))
);

-- System groups: non-members, members, board, officers
```

### group_members

```sql
CREATE TABLE group_members (
    group_id TEXT REFERENCES groups(id),
    user_id TEXT REFERENCES members(id),
    added_at TEXT DEFAULT (datetime('now')),
    added_by TEXT REFERENCES members(id),
    PRIMARY KEY (group_id, user_id)
);
```

### permissions

```sql
CREATE TABLE permissions (
    id TEXT PRIMARY KEY,
    module_id TEXT REFERENCES modules(id),
    slug TEXT NOT NULL,  -- 'view_proposals', 'create_proposals'
    name TEXT NOT NULL,
    description TEXT,
    UNIQUE(module_id, slug)
);
```

### group_permissions

```sql
CREATE TABLE group_permissions (
    group_id TEXT REFERENCES groups(id),
    permission_id TEXT REFERENCES permissions(id),
    PRIMARY KEY (group_id, permission_id)
);
```

### discussions

```sql
CREATE TABLE discussions (
    id TEXT PRIMARY KEY,
    group_id TEXT REFERENCES groups(id),  -- NULL = org-wide
    title TEXT NOT NULL,
    status TEXT DEFAULT 'open',  -- open, closed, archived
    created_by TEXT REFERENCES members(id),
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE discussion_messages (
    id TEXT PRIMARY KEY,
    discussion_id TEXT REFERENCES discussions(id),
    user_id TEXT REFERENCES members(id),
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT
);
```

---

## DTO Patterns

### Response DTOs

Located in `backend/internal/dto/responses.go`:

```go
// Use pointers for optional fields
type MemberResponse struct {
    ID            string   `json:"id"`
    FullName      string   `json:"full_name"`
    Status        string   `json:"status"`
    JoinedAt      *string  `json:"joined_at,omitempty"`  // pointer = optional
    Roles         []RoleResponse `json:"roles,omitempty"`
}

// Computed fields are fine
type MemberResponse struct {
    // ... db fields ...
    TotalEquity   string  `json:"total_equity"`  // calculated
    Initials      string  `json:"initials"`      // calculated
}
```

### Null Handling

Helper functions for SQL null types:

```go
// Convert sql.NullString to *string
func nullStr(ns sql.NullString) *string {
    if ns.Valid {
        return &ns.String
    }
    return nil
}

// Convert sql.NullInt64 to *int
func nullInt(ni sql.NullInt64) *int {
    if ni.Valid {
        v := int(ni.Int64)
        return &v
    }
    return nil
}

// String value or default
func nullStrVal(ns sql.NullString) string {
    if ns.Valid {
        return ns.String
    }
    return ""
}
```

---

## Query Patterns

### List Query

```go
func (h *Handlers) fetchProposals() ([]dto.ProposalResponse, error) {
    rows, err := h.db.Query(`
        SELECT p.id, p.title, p.status, p.created_at,
               m.full_name as proposer_name
        FROM proposals p
        LEFT JOIN members m ON m.id = p.proposed_by
        ORDER BY p.created_at DESC
    `)
    if err != nil {
        return nil, fmt.Errorf("query proposals: %w", err)
    }
    defer rows.Close()

    var proposals []dto.ProposalResponse
    for rows.Next() {
        var p dto.ProposalResponse
        var proposerName sql.NullString
        if err := rows.Scan(&p.ID, &p.Title, &p.Status, &p.CreatedAt, &proposerName); err != nil {
            return nil, fmt.Errorf("scan proposal: %w", err)
        }
        p.ProposerName = nullStr(proposerName)
        proposals = append(proposals, p)
    }

    return proposals, rows.Err()
}
```

### Detail Query

```go
func (h *Handlers) getProposal(id string) (*dto.ProposalResponse, error) {
    var p dto.ProposalResponse
    var proposerName, body sql.NullString

    err := h.db.QueryRow(`
        SELECT p.id, p.title, p.body, p.status, p.created_at,
               m.full_name as proposer_name
        FROM proposals p
        LEFT JOIN members m ON m.id = p.proposed_by
        WHERE p.id = ?
    `, id).Scan(&p.ID, &p.Title, &body, &p.Status, &p.CreatedAt, &proposerName)

    if err == sql.ErrNoRows {
        return nil, nil  // Not found
    }
    if err != nil {
        return nil, fmt.Errorf("query proposal %s: %w", id, err)
    }

    p.Body = nullStr(body)
    p.ProposerName = nullStr(proposerName)
    return &p, nil
}
```

### Batch Query (Avoiding N+1)

```go
func (h *Handlers) fetchMeetingsWithResolutions() ([]dto.MeetingResponse, error) {
    // 1. Fetch all meetings
    meetings, err := h.fetchMeetings()
    if err != nil {
        return nil, err
    }

    // 2. Collect meeting IDs
    ids := make([]string, len(meetings))
    for i, m := range meetings {
        ids[i] = m.ID
    }

    // 3. Batch fetch resolutions
    resolutions, err := h.fetchResolutionsByMeetingIDs(ids)
    if err != nil {
        return nil, err
    }

    // 4. Group by meeting ID
    resByMeeting := make(map[string][]dto.ResolutionResponse)
    for _, r := range resolutions {
        if r.MeetingID != nil {
            resByMeeting[*r.MeetingID] = append(resByMeeting[*r.MeetingID], r)
        }
    }

    // 5. Attach to meetings
    for i := range meetings {
        meetings[i].Resolutions = resByMeeting[meetings[i].ID]
    }

    return meetings, nil
}
```

### Insert Query

```go
func (h *Handlers) createProposal(title, body, proposedBy string) (string, error) {
    id := uuid.New().String()

    _, err := h.db.Exec(`
        INSERT INTO proposals (id, title, body, status, proposed_by, created_at)
        VALUES (?, ?, ?, 'draft', ?, datetime('now'))
    `, id, title, body, proposedBy)

    if err != nil {
        return "", fmt.Errorf("insert proposal: %w", err)
    }

    return id, nil
}
```

### Update Query

```go
func (h *Handlers) updateProposalStatus(id, status string) error {
    result, err := h.db.Exec(`
        UPDATE proposals
        SET status = ?, updated_at = datetime('now')
        WHERE id = ?
    `, status, id)

    if err != nil {
        return fmt.Errorf("update proposal status: %w", err)
    }

    rows, _ := result.RowsAffected()
    if rows == 0 {
        return fmt.Errorf("proposal %s not found", id)
    }

    return nil
}
```

---

## Migrations

### Creating a Migration

```bash
# Create new migration file
touch backend/migrations/012_add_feature.sql
```

### Migration Structure

```sql
-- 012_add_feature.sql

-- Schema changes
ALTER TABLE proposals ADD COLUMN new_field TEXT;

-- Seed data (if needed)
INSERT INTO proposals (id, title, status) VALUES
('prop-new-001', 'New Proposal', 'draft');

-- Indexes (always add for foreign keys and frequently queried fields)
CREATE INDEX IF NOT EXISTS idx_proposals_new_field ON proposals(new_field);
```

### Running Migrations

Migrations run automatically on app startup. To verify:

```bash
docker compose exec app sqlite3 /app/data/coop.db ".schema proposals"
```

---

## Testing Queries

### Interactive SQLite

```bash
docker compose exec app sqlite3 /app/data/coop.db

# Common commands
.tables              -- List tables
.schema proposals    -- Show table schema
SELECT * FROM proposals LIMIT 5;
```

### From Host (if sqlite3 installed)

```bash
sqlite3 backend/data/coop.db ".schema"
```

---

## Performance Tips

1. **Always add indexes for foreign keys**
   ```sql
   CREATE INDEX idx_proposals_proposed_by ON proposals(proposed_by);
   ```

2. **Batch fetch related data** - avoid N+1 queries

3. **Use LIMIT for list views**
   ```sql
   SELECT * FROM proposals ORDER BY created_at DESC LIMIT 50
   ```

4. **Use parameterized queries** - prevent SQL injection
   ```go
   h.db.Query("SELECT * FROM proposals WHERE id = ?", id)  // GOOD
   h.db.Query("SELECT * FROM proposals WHERE id = '" + id + "'")  // BAD
   ```
