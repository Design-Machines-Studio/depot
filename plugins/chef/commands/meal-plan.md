---
name: meal-plan
description: Generate a meal plan following Eve Persak's timing framework
argument-hint: "[number of days, any constraints or preferences]"
---

# Meal Plan

Generate a meal plan that follows Eve Persak's meal timing framework, balances nutrition across the week, and optionally schedules to Apple Calendar.

## Process

### Step 1: Understand Constraints

Parse the user's request for:

- Number of days (default: 7)
- Dietary constraints or preferences for the period
- Any planned dining out nights
- Any indulgence nights requested (pizza, pasta, ramen, etc.)
- Specific ingredients to use up
- Budget considerations

### Step 2: Load References

Read these files:

- `plugins/chef/skills/cooking/references/dietary-framework.md` -- Eve's meal timing and dietary rules
- `plugins/chef/skills/cooking/references/eve-recipes.md` -- Eve's recipe patterns for inspiration

Also check Mela for existing recipes by querying the SQLite database directly (see `plugins/chef/skills/cooking/references/mela-database.md`). Browse favorites, want-to-cook, or search by title/ingredients to reuse what Travis already has.

### Step 3: Build the Plan

Follow Eve's meal timing pattern for each day:

**Morning (6:30-7am):**

- Small, savory, high-protein. NOT sweet.
- Examples: eggs + avocado, Greek yogurt + berries, egg white omelet with vegetables
- Keep it simple and repeatable -- mornings do not need variety every day

**Midday (around 12pm):**

- Best time for carbohydrates. Include whole grains here.
- Protein + vegetables + moderate whole carbs
- Can be more substantial than other meals

**Afternoon Snack:**

- 30-40g nuts/seeds (walnuts, almonds, Brazil nuts)
- No need to vary much -- consistency is fine

**Dinner (6-7pm):**

- Low-carb focus. Protein + generous vegetables + healthy fats
- 15-20% smaller portions than Travis's current baseline
- Sheet pan meals, soups/stews, and grilled proteins work well here

**Design principles:**

- Rotate proteins across the week (do not repeat the same protein 3 nights running)
- Prioritize seafood 3-4 dinners per week (Eve's #1 protein)
- Include 1-2 legume-based meals per week
- Poultry 1-2 times per week
- Red meat 0-1 times per week (1-2x per month target)
- Plan 1 indulgence night if requested (pizza, pasta, etc.) -- position it at lunch when carb tolerance is highest
- Identify batch-cooking opportunities (cook rice once for 3 days, make a big batch of chimichurri, prep a soup base)
- Account for dining out -- suggest how to order well at Ubud restaurants

### Step 4: Present the Plan

Format as a table:

```
## Week of [date range]

| Day | Morning | Lunch | Dinner | Notes |
|-----|---------|-------|--------|-------|
| Mon | 2 eggs + avocado | Salmon quinoa bowl | Sheet pan shrimp fajitas | Batch chimichurri |
| Tue | Greek yogurt + berries | Chicken lentil curry | Baked cod + roast veg | Use leftover chimichurri |
| ... | ... | ... | ... | ... |

### Batch Prep (Sunday or Monday)
- Cook brown rice (use for Tue/Wed/Thu lunches, reheat for resistant starch)
- Make chimichurri (Mon/Tue/Wed)
- Wash and prep salad greens

### Shopping Summary
[Key ingredients needed -- use /shop for full store-by-store list]
```

### Step 5: Schedule (Optional)

Ask if Travis wants to schedule meals to Apple Calendar:

- Use Google Calendar MCP tools (`gcal_create_event`) to create events for each meal
- Default times: Morning 7:00, Lunch 12:00, Dinner 18:30
- Only schedule if the user confirms
