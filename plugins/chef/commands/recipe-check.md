---
name: recipe-check
description: Analyze a recipe against Eve Persak's dietary framework
argument-hint: "[paste recipe text, URL, or Mela recipe name]"
---

# Recipe Check

Quick recipe analysis against Eve's dietary framework. For full adapted recipes, use `/recipe-convert`.

## Process

### Step 1: Get the Recipe

Determine the input type and retrieve the recipe:

- **URL:** Fetch the page using WebFetch. Extract the recipe content (title, ingredients, instructions).
- **Mela recipe name:** Search Mela using `search_recipes(query)`, then `get_recipe(recipe_id)` to get full details.
- **Pasted text:** Parse the recipe directly from the user's input.
- **Described dish:** Ask the user for more detail if needed, or analyze the described version.

### Step 2: Load the Dietary Framework

Read `plugins/chef/skills/cooking/references/dietary-framework.md` to have Eve's complete guidelines available.

### Step 3: Analyze and Rate

Follow the analysis protocol defined in the recipe-analyzer agent: evaluate all 8 dimensions (protein hierarchy, fat sources, carb quality, glycemic impact, portion sizing, saturated fat, processed ingredients, meal slot fit), then rate as Aligned / Needs Tweaks / Needs Rework.

### Step 4: Report

Present findings in this format:

```
## [Recipe Name] -- [Rating]

### Issues

| Issue | Detail | Impact |
|-------|--------|--------|
| [ingredient/technique] | [what's wrong] | [Travis/Lydia/Both] |

### Modifications

1. [Specific, actionable change with food science reasoning]
2. [Next change...]
```

For each modification, explain the food science or nutritional reasoning. Not "use less butter" but "swap 30g butter for 2 tbsp olive oil -- same richness via fat content but shifts from 65% saturated to 14% saturated, directly supporting LDL reduction."

If the recipe Needs Rework, suggest `/recipe-convert` for a full Mela-importable adaptation rather than rewriting inline.
