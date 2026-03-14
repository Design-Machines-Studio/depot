---
name: recipe-convert
description: Convert a recipe to a healthy, Bali-friendly version and export as a .melarecipe file
argument-hint: "[recipe name from Mela, URL, or paste recipe text]"
---

# Recipe Convert

Take an existing recipe, adapt it to Eve Persak's dietary framework with Bali-available ingredients, and export as a `.melarecipe` file for import into Mela.

## Process

### Step 1: Get the Original Recipe

Determine the input type and retrieve:

- **Mela recipe name:** Search using `search_recipes(query)`, then `get_recipe(recipe_id)` for full details.
- **URL:** Fetch with WebFetch. Extract title, ingredients, instructions, yield, times.
- **Pasted text:** Parse directly.

### Step 2: Load References

Read these files:

- `plugins/chef/skills/cooking/references/dietary-framework.md` -- Eve's guidelines for what to change
- `plugins/chef/skills/cooking/references/bali-sourcing.md` -- Local ingredient availability
- `plugins/chef/skills/cooking/references/mela-format.md` -- Output file format spec

### Step 3: Analyze and Adapt

Work through the recipe systematically:

**Protein swaps (follow Eve's hierarchy):**

- Red meat to poultry or seafood where the dish allows
- If red meat is essential to the dish's identity (e.g., beef bolognese), use grass-fed, lean cuts, smaller portions (120-150g max)
- Add legumes where they complement the dish

**Fat swaps:**

- Butter to extra-virgin olive oil (low heat) or avocado oil (high heat)
- Coconut milk/cream to cashew cream, or reduced-quantity coconut
- Cream to Greek yogurt (stir in off heat to prevent curdling)
- Reduce cheese to 25-30g per serving, used as flavor accent

**Carb swaps:**

- White rice to brown/red/black rice, or cauliflower rice for dinner
- White pasta to legume pasta (lentil, chickpea) or whole grain
- White flour to whole grain flour (note: may need hydration adjustment)
- White bread to Bali Buda Revita Loaf or whole grain
- Apply resistant starch technique where applicable (cook, chill, reheat)

**Sweetener swaps:**

- Granulated sugar to whole pureed fruit or small amount of dried fruit
- Honey/maple to date paste or fruit reduction (use sparingly)

**Ingredient sourcing:**

- Check each ingredient against Bali availability
- Suggest specific stores and products from the sourcing guide
- Flag items that need substitution and explain why the sub works

**Preserve the soul of the dish:**

- Do not turn a carbonara into a salad. Keep the dish recognizable.
- Explain the food science behind each swap so Travis understands WHY.
- If a swap would destroy the dish, say so and suggest a different approach (e.g., "make it an occasional indulgence at reduced portion" instead of butchering it).

### Step 4: Build the Adapted Recipe

Write the full adapted recipe with:

- Clear ingredient list with quantities (metric preferred, imperial in parentheses)
- Numbered instructions with temperatures and times
- Notes section explaining what changed and why
- Categorization tags from the cooking skill

### Step 5: Export as .melarecipe

Generate a `.melarecipe` JSON file following the format in `mela-format.md`:

1. Generate a UUID v4 for the `id` field.
2. Set `title` to "[Recipe Name] (Eve-Adapted)".
3. Set `text` to a brief description of the adapted version.
4. Set `categories` from the recipe tags (meal slot, health alignment, protein type, cuisine).
5. Populate `yield`, `prepTime`, `cookTime`, `totalTime`.
6. Format `ingredients` as newline-separated string with `#` headers for sections.
7. Format `instructions` as newline-separated steps with `#` headers for phases.
8. Write `notes` with the adaptation summary (what changed, why, sourcing tips).
9. Set `link` to the source URL if adapted from a web recipe.
10. Leave `images` as empty array.

Sanitize the slug: strip all path separators and non-alphanumeric characters (except hyphens), lowercase, restrict to `[a-z0-9-]`. Verify the final path resolves within `~/Downloads/` before writing.

Write the file to `~/Downloads/[recipe-name-slug].melarecipe`.

### Step 6: Present Summary

Show the user:

- Original vs adapted comparison (key changes)
- Food science reasoning for major swaps
- File path for the exported `.melarecipe`
- Import instructions: "Open the file in Finder, or drag it onto the Mela app to import"
