---
name: capture
description: Quick capture an observation to ai-memory
argument-hint: "<entity name> <observation text>"
---

# Quick Capture

Add an observation to an existing ai-memory entity without loading the full ai-memory skill.

## Process

### 1. Parse Arguments

Extract the entity name and observation text from the arguments.

If no arguments provided, ask:
- What entity? (person, project, concept, etc.)
- What observation?

### 2. Find Entity

Search ai-memory for the entity:

```
search_entities(query: "<entity name>")
```

If not found, ask whether to create it. If creating, also ask for entity type.

### 3. Add Observation

```
add_observation(entityName: "<entity>", contents: ["<observation text>"])
```

### 4. Save

```
save()
```

### 5. Confirm

```
Captured to [entity name]: "[observation text]"
```
