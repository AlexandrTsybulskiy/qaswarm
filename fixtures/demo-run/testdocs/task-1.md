---
slug: task-1
title: Show sprint dates
product: demo
task_id: 1
requirement: task-1
status: ready
fetched_at: 2026-08-14T09:00:00+03:00
next_id: 5
---

## Cases

### tc-1-1
title: Open settings
action: Open settings
expected: Menu item visible
status: active
tier: smoke

### tc-1-2
title: List sprints
action: GET /v1/sprints
expected: 200 list
status: active
tier: smoke

### tc-1-3
title: Drag item
action: Drag Tasks first
expected: Tasks first on bar
status: active

### tc-1-4
title: Reset
action: Confirm reset
expected: default layout
status: active

### tc-1-5
title: Hidden
action: Old step
expected: gone
status: orphan

## Checklist

- tc-1-1
- tc-1-2
- tc-1-3
- tc-1-4

## Gaps

- none

Did not write to Upservice or Testmo.
