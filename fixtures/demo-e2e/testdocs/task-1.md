---
slug: task-1
title: Show widget
product: demo
task_id: 1
requirement: task-1
status: ready
fetched_at: 2026-08-25T12:00:00+03:00
next_id: 4
---

## Cases

### tc-1-1
title: Widget visible
action: Open personal dashboard Web
expected: widget title is visible
status: active

### tc-1-2
title: API list
action: GET /v1/tasks
expected: 200 and non-empty list
status: active

### tc-1-3
title: Orphan old
action: Old step
expected: Old expect
status: orphan
