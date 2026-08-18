# Prior lessons check

Loaded by the assess phase only when the repository carries prior run
postmortems or codified lessons to check against. A repository with none never
loads this file.

#### Prior Lessons Check

If `tasks/lessons.md` exists in the project root (created by prior pipeline runs via `execution-orchestrator`), surface recent entries that may apply to this feature:

1. Run `test -f tasks/lessons.md && grep -A 3 "^## " tasks/lessons.md | head -60` to list the most recent lesson headings plus their first three lines.
2. Filter to entries modified in the last 60 days (use `git log --format=%ad --date=short tasks/lessons.md | head -5` to estimate recency if file-level mtime is unreliable).
3. Keyword-match lesson headings against the original prompt's key nouns -- if the lesson mentions any of those nouns, it is potentially relevant.
4. Record matches in the Assessment Brief under a `## Recent Lessons That May Apply` heading. Include the lesson heading and a one-line excerpt.

If no `tasks/lessons.md` exists, log `prior lessons check: no lessons file -- skipping` and continue.
