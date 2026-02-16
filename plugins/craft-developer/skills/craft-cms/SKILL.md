---
name: craft-cms
description: Professional Craft CMS development expertise for building sites, debugging issues, and providing community support. Use when working with Craft CMS templates (Twig), element queries, GraphQL API, Matrix fields, relational fields, eager loading, caching, plugins, or answering Craft CMS technical questions. Covers Craft 4 and Craft 5 patterns including breaking changes between versions.
---

# Craft CMS Developer

Professional patterns and solutions for Craft CMS development. Use this for building sites, debugging, or answering community questions.

## Core Concepts

### Element Queries

All content access starts with element queries. Chain parameters, then execute:

```twig
{% set posts = craft.entries()
  .section('blog')
  .orderBy('postDate DESC')
  .limit(10)
  .all() %}
```

**Execution methods:**
- `.all()` - Array of all results
- `.one()` - Single element or null
- `.exists()` - Boolean check
- `.count()` - Integer count
- `.ids()` - Array of IDs only

### Matrix Fields (Most Common Pain Point)

Matrix fields contain nested entries. Query the parent, access nested content:

```twig
{# Get parent entry #}
{% set recipe = craft.entries().section('recipes').slug('cookies').one() %}

{# Access Matrix field - returns entry query #}
{% set steps = recipe.recipeSteps.all() %}

{% for step in steps %}
  {# Each block is an entry with its own fields #}
  <div class="step">
    <h3>{{ step.title }}</h3>
    {{ step.instructions|md }}
  </div>
{% endfor %}
```

**Query entries WITH Matrix content:**
```twig
{# Entries that have at least one nested entry in Matrix field #}
{% set entries = craft.entries()
  .myMatrixField(':notempty:')
  .all() %}
```

**Craft 5 GraphQL for Matrix:**
```graphql
query RecipeSteps {
  entries(section: "recipes") {
    ... on recipe_Entry {
      recipeSteps {
        ... on step_Entry {
          title
          instructions
        }
      }
    }
  }
}
```

### Relational Queries (relatedTo)

The `relatedTo` parameter finds elements connected via relational fields.

**Direction matters:**
- `sourceElement` - "Find what THIS element points to"
- `targetElement` - "Find what points TO this element"

```twig
{# Products in this category (category is the target) #}
{% set products = craft.entries()
  .section('products')
  .relatedTo({
    targetElement: category,
    field: 'productCategories'
  })
  .all() %}

{# Categories this product belongs to (product is the source) #}
{% set categories = craft.categories()
  .relatedTo({
    sourceElement: product,
    field: 'productCategories'
  })
  .all() %}
```

**Combining conditions:**
```twig
{# AND - must match ALL #}
{% set results = craft.entries()
  .relatedTo(['and', category1, category2])
  .all() %}

{# OR (default) - match ANY #}
{% set results = craft.entries()
  .relatedTo([category1, category2])
  .all() %}
```

### Eager Loading (Performance)

Prevent N+1 queries when accessing related content in loops.

**Upfront eager loading:**
```twig
{% set posts = craft.entries()
  .section('blog')
  .with([
    'featureImage',
    'author',
    ['categories', { limit: 3 }],
  ])
  .all() %}
```

**Lazy eager loading (Craft 5+):**
```twig
{% for post in posts %}
  {% set image = post.featureImage.eagerly().one() %}
{% endfor %}
```

**Nested eager loading:**
```twig
{% set entries = craft.entries()
  .with([
    'matrixField.nestedAssetField',
    'matrixField.nestedEntriesField',
  ])
  .all() %}
```

## GraphQL Patterns

### Basic Entry Query
```graphql
query BlogPosts {
  entries(section: "blog", limit: 10, orderBy: "postDate DESC") {
    title
    url
    postDate @formatDateTime(format: "F j, Y")

    ... on post_Entry {
      summary
      featureImage {
        url @transform(width: 800, height: 600)
      }
    }
  }
}
```

### Filtering with Custom Fields
```graphql
query FilteredProducts {
  entries(section: "products", inStock: true, price: ">= 50") {
    title
    ... on product_Entry {
      price
      sku
    }
  }
}
```

### Matrix Field Mutations (Craft 5)
```graphql
mutation SaveRecipe {
  save_recipes_recipe_Entry(
    title: "New Recipe"
    steps: {
      entries: [
        {
          step: {
            instructions: "Step 1 content",
            id: "new:1"
          }
        }
      ],
      sortOrder: ["new:1"]
    }
  ) {
    id
    title
  }
}
```

## Craft 4 → 5 Breaking Changes

### Empty Array Behavior
**Craft 4:** Empty relatedTo arrays return all results
**Craft 5:** Empty arrays return NO results

```twig
{# WRONG in Craft 5 - returns nothing if categoryIds empty #}
{% set entries = craft.entries()
  .relatedTo(categoryIds)
  .all() %}

{# CORRECT - check first #}
{% set entries = craft.entries()
  .relatedTo(categoryIds|length ? categoryIds : null)
  .all() %}
```

### Matrix Block → Entry Terminology
- "Blocks" are now "nested entries"
- `blocks` parameter → `entries` in GraphQL mutations
- Block types → Entry types

### GraphQL Type Names
**Craft 4:** `news_article_Entry`
**Craft 5:** `article_Entry` (section prefix removed)

## Common Debugging

### Query Returns Nothing
1. Check `.status()` - drafts/disabled excluded by default
2. Check `.site()` - multi-site queries need explicit site
3. Check field handles - case-sensitive
4. Log the SQL: `{% dd craft.entries().section('x').getRawSql() %}`

### N+1 Query Issues
Symptom: Slow pages, many DB queries in debug toolbar
Solution: Add `.with([...])` to eagerly load relations

### Cache Not Clearing
Check what triggers invalidation:
- Entry save clears that entry's cache
- Template changes don't auto-clear
- Use cache tags for scoped invalidation:
```twig
{% cache using key "posts" tags ["section:blog"] %}
  ...
{% endcache %}
```

## Reference Files

For detailed patterns, see:
- `references/query-cookbook.md` - 30+ real-world query examples
- `references/graphql-patterns.md` - Complete GraphQL reference

## Community Support Tips

When helping in Discord/forums:
1. Ask for Craft version (4 vs 5 matters)
2. Request the actual Twig/PHP code, not description
3. Check if Matrix vs regular entries confusion
4. Suggest `.dd()` or `{% dd %}` for debugging
5. Link to specific docs section, not just "check docs"
