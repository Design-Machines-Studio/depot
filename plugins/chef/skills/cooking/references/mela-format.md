# Mela Recipe File Format

Reference for generating `.melarecipe` files that can be imported into the Mela app.

---

## File Types

- **`.melarecipe`** -- A single recipe. JSON file with the fields below.
- **`.melarecipes`** -- An archive of multiple recipes. A zip file containing one `.melarecipe` file per recipe.

---

## JSON Schema

```json
{
  "id": "string (required) -- UUID for new recipes, or URL without schema for web-sourced recipes",
  "title": "string -- recipe name",
  "text": "string -- short description, supports markdown links",
  "images": ["string -- base64-encoded image data"],
  "categories": ["string -- category names, no commas allowed in individual names"],
  "yield": "string -- servings (e.g. '4 servings')",
  "prepTime": "string -- preparation time (e.g. '15 min')",
  "cookTime": "string -- cooking time (e.g. '30 min')",
  "totalTime": "string -- combined time (e.g. '45 min')",
  "ingredients": "string -- newline-separated, supports # headers and markdown links",
  "instructions": "string -- newline-separated steps, supports # headers, **bold**, *italics*, links",
  "notes": "string -- post-instruction remarks, supports markdown",
  "nutrition": "string -- nutritional data, supports markdown",
  "link": "string -- recipe source (any string, not necessarily a URL)"
}
```

## Fields Ignored on Import

These fields exist in Mela's internal format but are ignored when importing:

- `favorite` (Bool) -- bookmark status
- `wantToCook` (Bool) -- to-cook list status
- `date` (Double) -- timestamp in seconds since January 1, 2001 UTC

---

## Formatting Conventions

### Ingredients Field

Use newlines to separate ingredients. Use `#` headers to group sections:

```
# Marinade
2 tbsp extra-virgin olive oil
3 cloves garlic, minced
1 lemon, juiced
1 tsp smoked paprika

# Main
500g wild-caught salmon fillet
400g broccoli florets
1 red bell pepper, sliced
```

### Instructions Field

Use newlines to separate steps. Supports `#` headers for phases, `**bold**` for emphasis, and markdown links:

```
# Prep
Combine olive oil, garlic, lemon juice, and paprika in a bowl.
Pat salmon dry and coat with marinade. Rest 15 minutes.

# Cook
Preheat oven to 200C (400F).
Toss vegetables with 1 tbsp olive oil on a sheet pan. Roast 10 minutes.
Add salmon to the pan. Roast another 12-15 minutes until salmon flakes easily.
```

### Categories

Use the recipe tag system from the cooking skill. Map tags to Mela categories:

- Meal slot: Morning, Lunch, Dinner, Snack
- Health alignment: Eve-Approved, Adapted, Indulgence
- Protein type: Seafood, Poultry, Eggs, Legumes
- Cuisine: Asian, Italian, Mediterranean, Mexican, Western

### Notes Field

Include adaptation notes explaining what was changed from the original and why:

```
**Adapted from:** [Original Recipe Name]
**Changes:** Swapped butter for olive oil (saturated fat reduction), replaced white pasta with legume pasta (fiber + lower glycemic index), reduced cheese from 100g to 25g (flavor accent only).
**Why:** Aligned with Eve's framework for Travis's cholesterol goals while preserving the dish's character.
```

---

## Generating Files

When creating `.melarecipe` files:

1. Generate a UUID v4 for the `id` field (or use the source URL without schema if adapted from a web recipe).
2. Set `title` to the recipe name. If adapted, append "(Eve-Adapted)" to the title.
3. Leave `images` as an empty array `[]` unless an image is available.
4. Populate `categories` from the recipe tag system.
5. Write the file with `.melarecipe` extension.
6. For batch exports, zip multiple `.melarecipe` files into a `.melarecipes` archive.

Default output directory: `~/Downloads/`
