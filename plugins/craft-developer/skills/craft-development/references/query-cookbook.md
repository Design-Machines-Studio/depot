# Craft CMS Query Cookbook

Real-world query patterns for common scenarios.

## Entry Queries

### Get entries with ANY of multiple categories
```twig
{% set posts = craft.entries()
  .section('blog')
  .relatedTo(categoryIds)
  .all() %}
```

### Get entries with ALL of multiple categories
```twig
{% set posts = craft.entries()
  .section('blog')
  .relatedTo(['and']|merge(categoryIds))
  .all() %}
```

### Get entries where one of two lightswitches is on
```twig
{% set entries = craft.entries()
  .section('products')
  .andWhere(['or',
    ['featuredHome', true],
    ['featuredCategory', true]
  ])
  .all() %}
```

### Search with fallback for empty query
```twig
{% set q = craft.app.request.getQueryParam('q') %}
{% set results = craft.entries()
  .section('blog')
  .search(q|length ? q : null)
  .all() %}
```

### Pagination
```twig
{% set limit = 12 %}
{% set page = craft.app.request.getQueryParam('page')|default(1) %}
{% set offset = (page - 1) * limit %}

{% set query = craft.entries()
  .section('products')
  .limit(limit)
  .offset(offset) %}

{% set entries = query.all() %}
{% set total = query.count() %}
{% set totalPages = (total / limit)|round(0, 'ceil') %}
```

### Get siblings of current entry
```twig
{% set siblings = craft.entries()
  .section(entry.section.handle)
  .id('not ' ~ entry.id)
  .orderBy('postDate DESC')
  .limit(3)
  .all() %}
```

### Get parent and children in structure
```twig
{# Parent #}
{% set parent = entry.getParent() %}

{# Immediate children #}
{% set children = entry.getChildren().all() %}

{# All descendants #}
{% set descendants = entry.getDescendants().all() %}

{# Ancestors (breadcrumbs) #}
{% set ancestors = entry.getAncestors().all() %}
```

### Entries by date range
```twig
{% set startDate = now|date_modify('-30 days')|atom %}
{% set endDate = now|atom %}

{% set recentPosts = craft.entries()
  .section('blog')
  .postDate(['and', ">= #{startDate}", "<= #{endDate}"])
  .all() %}
```

### Entries updated in last 7 days
```twig
{% set recentlyUpdated = craft.entries()
  .section('products')
  .dateUpdated('>= ' ~ now|date_modify('-7 days')|atom)
  .all() %}
```

## Asset Queries

### Get images only
```twig
{% set images = craft.assets()
  .volume('uploads')
  .kind('image')
  .all() %}
```

### Get assets by filename pattern
```twig
{% set pdfs = craft.assets()
  .volume('documents')
  .filename('*.pdf')
  .all() %}
```

### Get assets used in a field
```twig
{% set usedAssets = craft.assets()
  .relatedTo({
    sourceElement: entry,
    field: 'heroImage'
  })
  .all() %}
```

## Category/Tag Queries

### Get categories with entries
```twig
{% set categoriesWithPosts = craft.categories()
  .group('blogTopics')
  .relatedTo({
    sourceElement: craft.entries().section('blog').ids()
  })
  .all() %}
```

### Get category with entry count
```twig
{% for category in categories %}
  {% set count = craft.entries()
    .section('blog')
    .relatedTo(category)
    .count() %}
  {{ category.title }} ({{ count }})
{% endfor %}
```

## User Queries

### Get users by group
```twig
{% set authors = craft.users()
  .group('authors')
  .orderBy('lastName, firstName')
  .all() %}
```

### Get user with their entries
```twig
{% set author = craft.users().id(authorId).one() %}
{% set authorPosts = craft.entries()
  .section('blog')
  .authorId(author.id)
  .all() %}
```

## Matrix Field Queries

### Loop through Matrix with type checking
```twig
{% for block in entry.contentBlocks.all() %}
  {% switch block.type.handle %}
    {% case 'text' %}
      {{ block.body|md }}
    {% case 'image' %}
      {% set img = block.image.one() %}
      {% if img %}
        {{ img.getImg() }}
      {% endif %}
    {% case 'quote' %}
      <blockquote>{{ block.quoteText }}</blockquote>
    {% default %}
      {# Unknown block type #}
  {% endswitch %}
{% endfor %}
```

### Query specific Matrix entry types
```twig
{# Get only 'image' type nested entries #}
{% set imageBlocks = entry.contentBlocks
  .type('image')
  .all() %}
```

### Eager load Matrix nested content
```twig
{% set entries = craft.entries()
  .section('articles')
  .with([
    'contentBlocks',
    'contentBlocks.image:image',
    'contentBlocks.relatedEntries:link',
  ])
  .all() %}
```

### Lazy eager loading in loops (Craft 5+)

```twig
{% for recipe in recipes %}
  <h2>{{ recipe.title }}</h2>
  {{ recipe.steps.eagerly().count() }} Step(s)
  {% set image = recipe.featureImage.eagerly().one() %}
{% endfor %}
```

## Performance Patterns

### Avoid N+1 with eager loading
```twig
{# BAD - N+1 queries #}
{% for post in posts %}
  {% set image = post.featureImage.one() %}
{% endfor %}

{# GOOD - Single query #}
{% set posts = craft.entries()
  .section('blog')
  .with(['featureImage'])
  .all() %}
{% for post in posts %}
  {% set image = post.featureImage|first %}
{% endfor %}
```

### Count without fetching
```twig
{# BAD - fetches all entries just to count #}
{% set count = craft.entries().section('blog').all()|length %}

{# GOOD - COUNT query only #}
{% set count = craft.entries().section('blog').count() %}
```

### Check existence without fetching
```twig
{# BAD #}
{% if craft.entries().section('news').one() %}

{# GOOD #}
{% if craft.entries().section('news').exists() %}
```

### Get IDs only when that's all you need
```twig
{% set postIds = craft.entries()
  .section('blog')
  .ids() %}
```

## Advanced Query Params (5.6+)

### Custom field handles in orderBy

```twig
{% set products = craft.entries()
  .section('products')
  .orderBy('price ASC')
  .all() %}
```

### Custom field handles in where conditions

```twig
{% set expensive = craft.entries()
  .section('products')
  .andWhere(['>', 'price', 100])
  .all() %}
```

### Only canonical entries (no drafts/revisions, 5.7)

```twig
{% set entries = craft.entries()
  .section('blog')
  .canonicalsOnly(true)
  .all() %}
```

## Debugging Queries

### Print the SQL
```twig
{% set query = craft.entries().section('blog') %}
{{ query.getRawSql()|e }}
```

### Dump and die
```twig
{% dd craft.entries().section('blog').all() %}
```

### Check query params
```twig
{% set query = craft.entries().section('blog') %}
{{ dump(query.getCriteria()) }}
```
