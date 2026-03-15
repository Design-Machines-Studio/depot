# Mela Database Access

Direct SQLite access to Travis's Mela recipe database. Use this when reading, searching, tagging, or bulk-analyzing recipes.

---

## Database Location

```
~/Library/Group Containers/66JC38RDUD.recipes.mela/Data/Curcuma.sqlite
```

In Cowork, mount `~/Library/Group Containers` via `request_cowork_directory`, then access at:
```
/sessions/.../mnt/Group Containers/66JC38RDUD.recipes.mela/Data/Curcuma.sqlite
```

**Note:** `Shared.sqlite` exists in the same directory but is empty. Always use `Curcuma.sqlite`.

---

## Access Method

Use Python's built-in `sqlite3` module. The `sqlite3` CLI binary is not available in the Cowork VM.

```python
import sqlite3

db_path = '<mounted_path>/66JC38RDUD.recipes.mela/Data/Curcuma.sqlite'
db = sqlite3.connect(db_path)
cur = db.cursor()

# Always close when done
db.close()
```

---

## Schema

### ZRECIPEOBJECT (recipes)

| Column | Type | Description |
|--------|------|-------------|
| Z_PK | INTEGER | Primary key |
| Z_ENT | INTEGER | Core Data entity type (always 4) |
| Z_OPT | INTEGER | Core Data optimistic locking |
| ZTITLE | VARCHAR | Recipe name |
| ZINGREDIENTS | VARCHAR | Newline-separated ingredient list (may include `#` section headers) |
| ZINSTRUCTIONS | VARCHAR | Newline-separated steps |
| ZCOOKTIME | VARCHAR | e.g. "30 min" |
| ZPREPTIME | VARCHAR | e.g. "15 min" |
| ZTOTALTIME | VARCHAR | e.g. "45 min" |
| ZYIELD | VARCHAR | e.g. "4 servings" |
| ZFAVORITE | INTEGER | 1 = favorited, 0 = not |
| ZWANTTOCOOK | INTEGER | 1 = on want-to-cook list |
| ZLINK | VARCHAR | Source URL |
| ZNUTRITION | VARCHAR | Nutritional info (often empty) |
| ZTEXT | VARCHAR | Description/notes |
| ZCATEGORIES | VARCHAR | Comma-separated category list |
| ZNOTES | VARCHAR | Additional notes |

### ZRECIPETAG (tags)

| Column | Type | Description |
|--------|------|-------------|
| Z_PK | INTEGER | Primary key |
| Z_ENT | INTEGER | Core Data entity type (always 5) |
| Z_OPT | INTEGER | Core Data optimistic locking |
| ZTITLE | VARCHAR | Tag name |

### Z_4TAGS (recipe-tag join table)

| Column | Type | Description |
|--------|------|-------------|
| Z_4RECIPES | INTEGER | FK to ZRECIPEOBJECT.Z_PK |
| Z_5TAGS | INTEGER | FK to ZRECIPETAG.Z_PK |

Unique constraint on (Z_4RECIPES, Z_5TAGS) -- no duplicate tag assignments.

### ZRECIPEIMAGEOBJECT (recipe images)

| Column | Type | Description |
|--------|------|-------------|
| Z_PK | INTEGER | Primary key |
| ZRECIPE | INTEGER | FK to ZRECIPEOBJECT.Z_PK |
| ZIMAGE | BLOB | Image data |

### Z_PRIMARYKEY (entity counters)

Tracks the next available PK for each entity type. Relevant entries:

| Z_NAME | Z_SUPER | Z_MAX |
|--------|---------|-------|
| RecipeObject | 0 | (current max PK) |
| RecipeTag | 0 | (current max PK) |

---

## Current Tags

As of March 2026 (Z_PK → name):

| Z_PK | Tag Name | Notes |
|------|----------|-------|
| 1 | Breakfast | |
| 2 | Sauce | |
| 3 | Treats | |
| 4 | Soup | |
| 5 | Dinner | |
| 6 | Cocktail | |
| 7 | Vegetarian | |
| 8 | Mexican | |
| 9 | Dessert | |
| 10 | Sides | |
| 11 | Chinese | |
| 12 | Sandwiches | |
| 13 | Pizza | |
| 14 | Projects | |
| 15 | Beverage | |
| 16 | Indian | |
| 17 | Quick | |
| 18 | Vegan | |
| 19 | Salad | |
| 20 | Pasta | |
| 21 | Eve approved | Gold Standard: Eve-Approved + Bali-sourceable + Lydia-safe |

---

## Common Query Patterns

### Search recipes by title

```python
cur.execute("SELECT Z_PK, ZTITLE FROM ZRECIPEOBJECT WHERE ZTITLE LIKE ?", ('%chicken%',))
```

### Get full recipe by PK

```python
cur.execute("""
    SELECT ZTITLE, ZINGREDIENTS, ZINSTRUCTIONS, ZCOOKTIME, ZPREPTIME,
           ZTOTALTIME, ZYIELD, ZFAVORITE, ZWANTTOCOOK, ZLINK, ZNUTRITION
    FROM ZRECIPEOBJECT WHERE Z_PK = ?
""", (pk,))
```

### Get all recipes with a specific tag

```python
cur.execute("""
    SELECT r.Z_PK, r.ZTITLE
    FROM ZRECIPEOBJECT r
    JOIN Z_4TAGS t ON r.Z_PK = t.Z_4RECIPES
    WHERE t.Z_5TAGS = ?
    ORDER BY r.ZTITLE
""", (tag_pk,))
```

### Get all tags for a recipe

```python
cur.execute("""
    SELECT t.Z_PK, t.ZTITLE
    FROM ZRECIPETAG t
    JOIN Z_4TAGS jt ON t.Z_PK = jt.Z_5TAGS
    WHERE jt.Z_4RECIPES = ?
""", (recipe_pk,))
```

### List all favorites

```python
cur.execute("SELECT Z_PK, ZTITLE FROM ZRECIPEOBJECT WHERE ZFAVORITE = 1 ORDER BY ZTITLE")
```

### List want-to-cook

```python
cur.execute("SELECT Z_PK, ZTITLE FROM ZRECIPEOBJECT WHERE ZWANTTOCOOK = 1 ORDER BY ZTITLE")
```

### Export all recipes as JSON

```python
import json

cur.execute("""
    SELECT Z_PK, ZTITLE, ZINGREDIENTS, ZINSTRUCTIONS, ZCOOKTIME,
           ZPREPTIME, ZTOTALTIME, ZYIELD, ZFAVORITE, ZWANTTOCOOK, ZLINK, ZNUTRITION
    FROM ZRECIPEOBJECT ORDER BY ZTITLE
""")
columns = ['pk', 'title', 'ingredients', 'instructions', 'cooktime',
           'preptime', 'totaltime', 'yield', 'favorite', 'want_to_cook', 'link', 'nutrition']
recipes = [dict(zip(columns, row)) for row in cur.fetchall()]
```

---

## Tagging Recipes

### Add a tag to a recipe

```python
# Check if tag assignment already exists
cur.execute("SELECT 1 FROM Z_4TAGS WHERE Z_4RECIPES = ? AND Z_5TAGS = ?", (recipe_pk, tag_pk))
if not cur.fetchone():
    cur.execute("INSERT INTO Z_4TAGS (Z_4RECIPES, Z_5TAGS) VALUES (?, ?)", (recipe_pk, tag_pk))
    db.commit()
```

### Bulk tag recipes (safe, deduplicated)

```python
# Clear existing tags for this tag type, then re-insert
EVE_TAG_PK = 21
cur.execute("DELETE FROM Z_4TAGS WHERE Z_5TAGS = ?", (EVE_TAG_PK,))

# Build deduplicated recipe PK set (handle duplicate titles)
recipe_map = {}
cur.execute("SELECT Z_PK, ZTITLE FROM ZRECIPEOBJECT")
for pk, title in cur.fetchall():
    if title not in recipe_map:
        recipe_map[title] = pk

# Insert tags
for pk in target_pks:
    cur.execute("INSERT INTO Z_4TAGS (Z_4RECIPES, Z_5TAGS) VALUES (?, ?)", (pk, EVE_TAG_PK))
db.commit()
```

### Create a new tag

```python
# Get the next PK
cur.execute("SELECT Z_MAX FROM Z_PRIMARYKEY WHERE Z_NAME = 'RecipeTag'")
max_pk = cur.fetchone()[0]
new_pk = max_pk + 1

# Insert the tag (Z_ENT=5 for RecipeTag)
cur.execute("INSERT INTO ZRECIPETAG (Z_PK, Z_ENT, Z_OPT, ZTITLE) VALUES (?, 5, 1, ?)", (new_pk, 'New Tag Name'))

# Update the PK counter
cur.execute("UPDATE Z_PRIMARYKEY SET Z_MAX = ? WHERE Z_NAME = 'RecipeTag'", (new_pk,))
db.commit()
```

### Remove a tag from a recipe

```python
cur.execute("DELETE FROM Z_4TAGS WHERE Z_4RECIPES = ? AND Z_5TAGS = ?", (recipe_pk, tag_pk))
db.commit()
```

---

## Important Notes

- **Always commit** after writes: `db.commit()`
- **iCloud sync:** Changes sync to Mela on all devices. Mela may need to be relaunched to pick up direct DB changes immediately.
- **Duplicate titles:** Some recipes have identical titles. When matching by title, use a dict to get the first PK per title, or handle duplicates explicitly.
- **Core Data:** This is a Core Data SQLite store. The `Z_` prefix columns are Core Data internals. Don't modify `Z_ENT` or `Z_OPT` unless you understand the implications.
- **Backup:** Before bulk operations, consider copying the database file as a backup.
- **Recipe count:** As of March 2026, the database contains 329 recipes, 21 tags, and 321 images.
