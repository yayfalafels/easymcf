---
name: markdown-tables
description: generating, creating, manipulating and editing markdown tables in markdown files *.md
---

## DO NOT use line continuation breaks

whatever you do for markdown tables, never never never use line continuation breaks, inside or outside markdown tables.
line continuation breaks are only allowed inside code snippets in accordance with that coding style usage guide.

correct, no line continuation breaks:

```md
lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum 
```

appropriate usage of line continuation breaks inside code snippets:

```python
for i in range(10):       # you are supposed to break the line here
    print(i)
```

```bash
curl -X POST \
  -H "Content-Type: application/json" \     # this is also an acceptable use of line continuation breaks inside code snippets
  -d '{"key": "value"}' \
  http://example.com/api
```

INCORRECT!!! never do this! unless it is the appropriate usage inside code snippets

```md
lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum 
lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum 
lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum 
lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum lorum ipsum
 lorum ipsum lorum ipsum lorum ipsum 
```

## Markdown tables

Now that you are clear on the line continuation breaks, let's talk about markdown tables.

1. limit total row length to < 115 characters
2. pad to fixed width columns
3. use an id column to the left most column
4. for length columns, migrate to notes at the bottom of the table and reference using the row id

correctly formatted markdown table:

```md
| id | seq | status  | milestone                                | 
| -- | --- | ------- | ---------------------------------------- | 
| 01 | 01  | open    | scope requirements tasks                 | 
| 02 | 02  | pending | dev env setup postgresql db              | 
| 03 | 03  | pending | dev env setup spark container            | 

02. **postgresql setup** length commentary about setting up dev env for postgresql db, and how to do it, and what to do, and what not to do, and how to avoid pitfalls, and how to avoid mistakes, and how to avoid errors, and how to avoid problems, and how to avoid issues, and how to avoid complications, and how to avoid difficulties, and how to avoid challenges, and how to avoid obstacles, and how to avoid hindrances, and how to avoid impediments, and how to avoid setbacks, and how to avoid snags, and how to avoid glitches, and how to avoid malfunctions, and how to avoid breakdowns, and how to avoid failures, and how to avoid crashes, and how to avoid freezes, and how to avoid hangs, and how to avoid stalls, and how to avoid lags, and how to avoid delays, and how to avoid interruptions, and how to avoid disruptions, and how to avoid disturbances, and how to avoid interferences

```

incorrectly formatted markdown table:

```md
| status | milestone | 
| - | - | 
| open | scope requirements tasks | 
| pending | dev env setup postgresql db length commentary about setting up dev env for postgresql db, and how to do it, and what to do, and what not to do, and how to avoid pitfalls, and how to avoid mistakes, and how to avoid errors, and how to avoid problems, and how to avoid issues, and how to avoid complications, and how to avoid difficulties, and how to avoid challenges | 
| pending | dev env setup spark container | 

```