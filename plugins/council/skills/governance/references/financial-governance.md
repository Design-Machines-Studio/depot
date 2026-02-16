# Financial Governance Reference

*BC Cooperative Association Act compliance for Co-op OS*

---

## The Cooperative Financial Difference

Cooperatives handle money differently than traditional businesses. The Act encodes specific financial rules that distinguish co-ops:

1. **Patronage-based returns** - Surplus distributed by use, not ownership
2. **Limited return on capital** - Investment shares capped (8% default)
3. **Reserve requirements** - Building collective resilience
4. **Member equity tracking** - Individual capital accounts (ICAs)
5. **Solvency tests** - Protecting member interests

---

## Share Capital Structure

### Required: Membership Shares

**Section 48(1)(a):** Every association must have one class of membership shares.

**Options:**
- Par value (e.g., $100/share) - payable on call or fully paid
- No par value - determined by directors

**Section 30:** Membership shares required as condition of membership.

**Section 52:** Shares must be fully paid except:
- Membership shares with par value may be payable on call
- Calls made by directors per rules

### Optional: Investment Shares

**Section 48(1)(b):** May have one or more classes of investment shares.

**Section 49:** Investment shares may be issued to:
- Members
- Non-members (if memorandum/rules permit)

**Section 50:** Classes may have different rights regarding:
- Voting (but never exceed member voting power)
- Dividends
- Redemption
- Priority on dissolution

---

## Patronage Returns

### The Principle

**Section 9(1):** Association may allocate surplus to members based on business done during the year.

**This is the defining feature of cooperative economics** - surplus flows back to those who created it through their patronage, not to investors based on capital contribution.

### Calculation Methods

**Section 9(2):** Patronage may be calculated by:
- Quantity of products/commodities acquired
- Quantity of goods delivered or services rendered
- Quality of products/commodities/goods/services
- Value of products/commodities/goods/services

### Non-Member Patronage

**Section 9(3):** May distribute to non-member patrons IF:
- Rules expressly authorize
- Rate does not exceed rate to members

### Distribution Forms

Patronage can be distributed as:
1. **Cash** - Immediate payment
2. **Shares** - Additional membership or investment shares
3. **Deferred payment** - IOUs, patronage certificates
4. **Combination** - Part cash, part allocated

### Tax Implications (General)

*Note: Specific tax advice requires professional consultation.*

- Patronage allocations generally deductible to co-op
- Taxable to member when received (or when constructively received)
- Deferred allocations may have different treatment
- "20% rule" often applies (minimum cash distribution)

---

## Dividend Limits

### On Membership Shares

**Section 66(1)(c):** Dividends on membership shares cannot exceed:
- 8% per year, OR
- Higher percentage specified in rules

**Purpose:** Ensures capital doesn't dominate; aligns co-op with patronage principle.

### On Investment Shares

**Section 66(1)(b):** Dividends on investment shares as specified in memorandum and rules.

**No automatic cap** - but still subject to solvency test.

---

## Solvency Requirements

### The Solvency Test

**Section 66(2):** Association must NOT:
- Redeem shares, OR
- Pay dividends/patronage returns

IF doing so would render the association unable to pay its debts as they become due.

### When Applied

Before any:
- Share redemption (on withdrawal/termination)
- Dividend declaration
- Patronage distribution
- Major capital return

### Co-op OS Implementation

```yaml
solvency_check:
  date: YYYY-MM-DD
  proposed_distribution: amount
  current_assets: amount
  current_liabilities: amount
  near_term_obligations: list
  
  tests:
    quick_ratio: current_assets / current_liabilities
    cash_flow_adequate: boolean
    upcoming_obligations_covered: boolean
    
  result:
    passes_solvency: boolean
    maximum_safe_distribution: amount
    notes: explanation
```

---

## Reserve Requirements

### Model Rules Default (§149-154)

**Allocation formula by capital size:**

| Total Capital | Reserve Allocation |
|--------------|-------------------|
| ≤ $25,000 | 30% of surplus until reserves = capital |
| $25,001 - $50,000 | 20% of surplus until reserves = capital |
| $50,001 - $100,000 | 10% of surplus until reserves = capital |
| > $100,000 | As determined by members |

### Purpose of Reserves

- Absorb losses without affecting member equity
- Fund future growth/capital needs
- Provide stability during downturns
- Build collective wealth (indivisible)

### Indivisible vs. Divisible Reserves

**Indivisible reserves:**
- Not distributed to members on dissolution
- Often go to another co-op or co-op development fund
- Build sector-wide solidarity

**Divisible reserves:**
- May be distributed on dissolution
- Subject to rules and memorandum provisions

---

## Individual Capital Accounts (ICAs)

### What They Track

For each member:
```yaml
member_equity:
  member_id: reference
  
  membership_shares:
    class: membership
    quantity: number
    par_value: amount_per_share
    paid_up: amount
    on_call: amount_remaining
    
  patronage_allocated:
    - year: YYYY
      total_patronage: amount
      cash_paid: amount
      retained: amount
      
  total_equity: sum_of_all
  
  dates:
    joined: YYYY-MM-DD
    last_updated: YYYY-MM-DD
```

### On Withdrawal/Termination

**Section 38:** Association must redeem membership shares:
- Within period specified in rules, OR
- Immediately if no period specified

**Subject to solvency test** - can't pay if insolvent.

---

## Borrowing Powers

### Director Authority (Model Rules §137)

Directors may, without member approval:
- Borrow money
- Issue debt securities
- Give guarantees
- Mortgage/charge assets
- Invest funds

### Limits Requiring Member Approval

**Model Rules often specify:**
- Borrowing above X% of assets requires special resolution
- Major asset sales require member approval
- Guarantees for non-members may require approval

### Security Instruments

**Section 74(2)(d-f):** Directors may:
- Issue debentures
- Create security interests
- Give guarantees on behalf of association

---

## Financial Reporting Requirements

### Annual Financial Statements

**Section 153:** At AGM, directors must lay before members:
- Comparative financial statements (current + prior year)
- Auditor's report (if required)
- Any additional information required by rules

**Section 153(1)(b)(iv):** Financial statements must be sent to members at least **10 days before AGM**.

### What Statements Must Show

Per Generally Accepted Accounting Principles:
- Balance sheet (assets, liabilities, equity)
- Income statement (revenue, expenses, surplus/deficit)
- Statement of changes in equity
- Cash flow statement
- Notes to financial statements

### Member Equity Section

Should clearly show:
- Membership shares outstanding
- Investment shares by class
- Retained surplus
- Reserves (divisible and indivisible)
- Current year surplus/deficit
- Patronage allocated (cash and retained)

---

## Audit Requirements

### Who Needs an Auditor

**Section 108:** Every association must appoint an auditor UNLESS:
- Exempted under s.109

### Exemption Criteria (s.109)

Association may be exempt if:
- Revenue below prescribed threshold, AND
- Members pass resolution dispensing with audit

**Model Rules alternative:** May appoint "financial reviewer" instead of auditor for smaller co-ops.

### Auditor Duties

**Section 114:** Auditor must:
- Audit financial statements
- Report whether statements present fairly
- State basis of opinion

### Auditor Rights

- Access to all records (s.117)
- Entitled to attend all meetings (s.120)
- Right to be heard on relevant matters (s.122)
- Notice of meetings (s.122)

---

## Annual Report Filing

### Requirements

**Section 126:** Every association must file annual report with registrar:
- Within 2 months after each AGM
- Form prescribed by registrar
- Filing fee (currently $30)

### Consequences of Non-Filing

**Section 194.4:** Registrar may dissolve association that fails to file.

**Financial penalty:** Late fees may apply.

---

## Co-op OS Financial Modules

### Tier 1: Equity Tracking (MVP)

```yaml
member_shares:
  - track membership shares per member
  - par value and paid-up status
  - share transfers and redemptions
  
patronage_basic:
  - annual patronage allocation records
  - cash vs. retained splits
  - member-level detail
```

### Tier 2: Financial Management (Core)

```yaml
reserve_management:
  - reserve calculations per Model Rules
  - reserve fund tracking
  - allocation workflow
  
solvency_checks:
  - pre-distribution solvency tests
  - dashboard warnings
  - documentation trail
  
dividend_management:
  - dividend declarations
  - limit enforcement (8% cap)
  - payment tracking
```

### Tier 3: Advanced Financial (Advanced)

```yaml
investment_shares:
  - multiple share classes
  - class-specific rights
  - separate resolutions tracking
  
ica_management:
  - full individual capital accounts
  - deferred patronage tracking
  - equity projections
  
financial_reporting:
  - statement generation
  - member equity schedules
  - regulatory report preparation
```

---

## Integration with Slate/Mario's Work

### Data Co-op OS Receives from Bookkeeping

```yaml
from_slate:
  net_surplus: annual figure
  cash_available: for distributions
  current_ratio: assets/liabilities
  member_hours: if tracked externally
  revenue_by_member: if trackable
```

### Data Co-op OS Provides

```yaml
to_slate:
  member_list: current and former
  share_register: for balance sheet
  patronage_allocations: for tax reporting
  distribution_records: what was paid
```

### Integration Triggers

- Slate provides surplus → Co-op OS calculates patronage
- Co-op OS approves distribution → Slate processes payments
- Member joins/leaves → both systems update

---

## Red Flags: Financial Governance

| Warning Sign | Risk Level | Action |
|--------------|------------|--------|
| No solvency check before distribution | High | Block distribution, require check |
| Membership dividends > 8% | High | Reject unless rules authorize higher |
| Reserve allocation skipped | Medium | Flag for review, may violate rules |
| ICA records out of date | Medium | Reconciliation needed |
| Financial statements not sent 10 days before AGM | High | AGM decisions may be challenged |
| No audit when required | High | Compliance failure |
| Shares redeemed during insolvency | Critical | Personal liability risk |

---

## Quick Reference: Key Financial Limits

| Item | Default Limit | Source |
|------|---------------|--------|
| Membership share dividends | 8%/year max | s.66(1)(c) |
| Investment share dividends | Per memorandum/rules | s.66(1)(b) |
| Non-member patronage rate | ≤ member rate | s.9(3) |
| Financial statements timing | 10 days before AGM | s.153(1)(b)(iv) |
| Annual report filing | 2 months after AGM | s.126 |
| Share redemption timing | Per rules, or immediate | s.38 |
| Reserve allocation | Per Model Rules formula | Model Rules §149-154 |

---

*Reference v1.0 · February 2026*
*Source: BC Cooperative Association Act (SBC 1999, c.28)*
