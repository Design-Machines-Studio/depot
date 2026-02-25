# Craft CMS GraphQL Patterns

Complete GraphQL reference for headless Craft CMS development.

## Query Fundamentals

### Section-specific query
```graphql
query BlogPosts {
  blogEntries(limit: 10, orderBy: "postDate DESC") {
    title
    url
    ... on post_Entry {
      summary
    }
  }
}
```

### Generic entries query
```graphql
query AllNews {
  entries(section: "news", status: "live") {
    title
    url
    dateCreated @formatDateTime(format: "Y-m-d")
  }
}
```

### Entry by slug
```graphql
query SinglePost($slug: [String]) {
  entry(section: "blog", slug: $slug) {
    title
    ... on post_Entry {
      body
      featureImage {
        url
      }
    }
  }
}
```

## Inline Fragments (Type-specific fields)

```graphql
query MixedContent {
  entries(section: "content") {
    title

    # Fields specific to 'article' entry type
    ... on article_Entry {
      body
      author {
        fullName
      }
    }

    # Fields specific to 'video' entry type
    ... on video_Entry {
      videoUrl
      duration
    }
  }
}
```

## Relational Fields

### Assets
```graphql
query WithImages {
  entries(section: "products") {
    ... on product_Entry {
      title
      productImages {
        url
        width
        height
        url @transform(width: 800, height: 600, quality: 80)
      }
    }
  }
}
```

### Categories/Tags
```graphql
query WithCategories {
  entries(section: "blog") {
    ... on post_Entry {
      title
      topics {
        title
        slug
      }
    }
  }
}
```

### Related entries
```graphql
query WithRelated {
  entries(section: "products") {
    ... on product_Entry {
      title
      relatedProducts {
        title
        url
      }
    }
  }
}
```

## Matrix Fields

### Craft 5 pattern
```graphql
query RecipeWithSteps {
  entry(section: "recipes", slug: "chocolate-cookies") {
    ... on recipe_Entry {
      title
      steps {
        ... on step_Entry {
          title
          instructions
          estimatedTime
        }
      }
    }
  }
}
```

### Field-specific Matrix query
```graphql
query HardSteps {
  stepsFieldEntries(difficulty: "hard") {
    ... on step_Entry {
      title
      estimatedTime
    }
  }
}
```

### Generic Matrix query with field argument
```graphql
query FilteredSteps {
  entries(field: "steps", difficulty: "hard") {
    ... on step_Entry {
      title
      instructions
    }
  }
}
```

## Directives

### Format dates
```graphql
query Dates {
  entries(section: "events") {
    title
    postDate @formatDateTime(format: "F j, Y")
    eventDate @formatDateTime(format: "l, F j, Y \\a\\t g:i A")
  }
}
```

### Transform images
```graphql
query Images {
  assets(volume: "uploads") {
    filename
    url
    thumbnail: url @transform(width: 150, height: 150, mode: "crop")
    hero: url @transform(width: 1200, height: 600, quality: 90)
  }
}
```

### Markdown processing
```graphql
query Content {
  entry(section: "about") {
    ... on about_Entry {
      bio @markdown
    }
  }
}
```

## Filtering

### By custom fields
```graphql
query FilteredProducts {
  entries(section: "products", inStock: true, price: ">= 100") {
    title
    ... on product_Entry {
      price
      inStock
    }
  }
}
```

### By relation
```graphql
query RelatedPosts {
  entries(
    section: "blog"
    relatedToCategories: [
      { slug: "technology", group: "topics" }
    ]
  ) {
    title
    url
  }
}
```

### By date
```graphql
query RecentPosts {
  entries(section: "blog", postDate: ">= 2024-01-01") {
    title
    postDate @formatDateTime(format: "Y-m-d")
  }
}
```

### Combined filters
```graphql
query Featured {
  entries(
    section: "products"
    featured: true
    status: "live"
    orderBy: "title ASC"
    limit: 6
  ) {
    title
    url
  }
}
```

## Mutations

### Save entry
```graphql
mutation CreatePost($title: String!, $body: String) {
  save_blog_post_Entry(
    title: $title
    body: $body
    authorId: 1
  ) {
    id
    uid
    dateCreated @formatDateTime(format: "c")
  }
}
```

### Save with Matrix (Craft 5)
```graphql
mutation CreateRecipe {
  save_recipes_recipe_Entry(
    title: "New Recipe"
    steps: {
      entries: [
        {
          step: {
            instructions: "Preheat oven to 350°F",
            estimatedTime: 5,
            id: "new:1"
          }
        },
        {
          step: {
            instructions: "Mix ingredients",
            estimatedTime: 10,
            id: "new:2"
          }
        }
      ],
      sortOrder: ["new:1", "new:2"]
    }
  ) {
    id
    title
  }
}
```

### Delete entry
```graphql
mutation DeletePost($id: Int!) {
  deleteEntry(id: $id)
}
```

## Global Sets

```graphql
query SiteSettings {
  globalSet(handle: "siteSettings") {
    ... on siteSettings_GlobalSet {
      siteName
      tagline
      socialLinks {
        platform
        url
      }
    }
  }
}
```

## Aggregates

### Entry count
```graphql
query Stats {
  postCount: entryCount(section: "blog")
  productCount: entryCount(section: "products", inStock: true)
}
```

### Grouped counts
```graphql
query CategoryCounts {
  positive: entryCount(section: "reviews", sentiment: "positive")
  negative: entryCount(section: "reviews", sentiment: "negative")
  neutral: entryCount(section: "reviews", sentiment: ["neutral", null])
}
```

## Craft 4 vs 5 Differences

### Type naming
```graphql
# Craft 4
... on news_article_Entry { }

# Craft 5
... on article_Entry { }
```

### Matrix mutations
```graphql
# Craft 4
ingredients: { blocks: [...] }

# Craft 5
ingredients: { entries: [...] }
```

### Empty array behavior
```graphql
# Craft 4: returns all if empty array
entries(relatedTo: [])

# Craft 5: returns nothing if empty array
# Solution: Don't pass empty arrays, use null
```

## Singles Queries (5.8+)

Singles get dedicated GraphQL queries:

```graphql
query {
  homepageEntry {
    ... on homepage_Entry {
      heroTitle
      heroImage {
        url @transform(width: 1200, height: 600)
      }
    }
  }
}
```

No need for `entry(section: "homepage")` — use `<handle>Entry` directly.

## Advanced Query Arguments (5.7+)

```graphql
# Search with options (5.7)
query {
  entries(section: "blog", search: "craft cms", searchTermOptions: { subLeft: true }) {
    title
  }
}

# Include provisional drafts (5.7)
query {
  entries(section: "blog", withProvisionalDrafts: true) {
    title
    isDraft
  }
}
```

## Performance Tips

1. **Request only needed fields** - Don't fetch entire entries if you only need title/url
2. **Use pagination** - limit/offset for large result sets
3. **Batch queries** - Combine multiple queries in one request
4. **Use transforms** - Request specific image sizes, not full resolution
5. **Cache responses** - GraphQL responses are highly cacheable
6. **Preview tokens** (5.9) - Use `X-Craft-Preview-Token` header for preview API requests
