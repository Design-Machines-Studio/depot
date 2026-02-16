# Relationship Management

Relationship features for the AI Memory system via MCP tools.

## Querying Relationships

```
# Get all relationships for an entity (outgoing AND incoming)
get_relationships("Travis Gertz")

# Returns outgoing and incoming lists:
# Outgoing: Travis Gertz -> Lydia Lee (partner_of)
# Incoming: Pixel & Tonic -> Travis Gertz (employs)
```

## Common Relationship Types

| Type | Description |
|------|-------------|
| `owns` | Ownership relationship |
| `works_for` | Employment relationship |
| `works_on` | Project involvement |
| `partner_of` | Personal partner |
| `knows` | General acquaintance |
| `created` | Creator relationship |
| `located_in` | Location relationship |
| `member_of` | Group membership |
| `manages` | Management relationship |
| `reports_to` | Reporting relationship |

## Adding Relationships

```
# Create a new relationship (auto-saves)
add_relationship("Travis Gertz", "New Project", "created")

# Relationships are directional: from_entity -> to_entity
# Query from either side using get_relationships()
```

## Relationship Graph Patterns

### People Network
```
Travis Gertz
  partner_of -> Lydia Lee
  knows -> [Professional contacts]
  works_for <- Pixel & Tonic
  owns -> Design Machines
```

### Project Network
```
Design Machines (Company)
  owned_by <- Travis Gertz
  works_on -> [Active projects]
  located_in -> Bali
```

### Financial Tracking
```
Financial Entity
  tracks -> [Account balances]
  relates_to -> Design Machines
  temporal_series: true
```

## Best Practices

1. **Use consistent relationship types** - Check existing relationships before creating new types
2. **Bidirectional awareness** - Relationships are stored on one entity but queryable from both via `get_relationships()`
3. **Check existing relationships first** - Use `get_relationships()` before adding duplicates
