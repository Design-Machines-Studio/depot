# AI Memory Examples

Common workflows and patterns using MCP tools.

## Searching for Information

### Find a person
```
search_entities("Jane", 5)
# Returns matching entities with summaries

get_entity("Jane Gertz")
# Returns full entity details
```

### Find projects
```
search_entities("Design Machines", 5)
# Returns matching entities

list_entity_types()
# See all entity types with counts
```

### Search in observations
```
search_entities("Bali", 10)
# Searches across entity names, types, AND observation content
```

## Adding New Information

### Add a new person
```
search_entities("New Contact")
# First verify they don't already exist

add_entity("New Contact", "Person", ["Met at conference in Feb 2026", "Works in AI development"])
# Auto-saves, no manual save needed
```

### Add observation to existing entity
```
add_observation("Travis Gertz", "[Feb 2026] Started new project")
add_observation("Design Machines", "[Feb 2026] Q1 revenue exceeded targets")
# Both auto-save
```

### Delete observations with matching content

```
search_entities("Alex Johnson", 5)
# Find the entity to review observations

delete_observation("Alex Johnson", "Circle 3")
# Deletes all observations containing "Circle 3"
# Returns: deleted count and remaining count
```

### Edit observation at specific index
```
get_entity("Alex Johnson")
# Review observations to find the index to edit

edit_observation("Alex Johnson", 2, "[February 2026] Circle 2 - Inner Circle")
# Edits observation at index 2 (0-based)
# Returns: old content, new content, and observation count
```

### Create relationships
```
add_relationship("New Contact", "Design Machines", "knows_from")
add_relationship("Travis Gertz", "New Project", "created")
# Both auto-save
```

### Fix entity name (rename)

```
search_entities("James Mus", 5)
# Find the entity to confirm spelling

rename_entity("James Musilk", "James Musulk")
# Renames entity and updates all relationship references
# Returns: success status and count of updated references
```

## Investigating Connections

### Find all relationships for a person
```
get_relationships("Travis Gertz")
# Returns outgoing and incoming relationships
```

### Map project involvement
```
get_relationships("Design Machines")
# See all people, projects, and entities connected to Design Machines
```

## Financial Tracking

### Find financial entities
```
search_entities("budget", 10)
# Finds financial entities mentioning budget
```

### Add financial observation
```
add_observation("Monthly Budget Tracking", "[Feb 2026] Reserve fund updated")
```

## Health Tracking

### Query health data
```
search_entities("health", 10)
# Finds health-related entities
```

### Add health observation
```
add_observation("Health Tracking", "[Feb 2026] Annual checkup complete, all results normal")
```

## System Management

### Check system stats
```
get_stats()
# Returns entity count, type distribution, recent observations
```

### List all entity types
```
list_entity_types()
# Returns all types with counts, sorted by count
```
