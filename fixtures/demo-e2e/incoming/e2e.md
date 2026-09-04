---
slug: task-1
title: Show widget
product: demo
task_id: 1
testdoc: task-1
fetched_at: 2026-08-25T12:05:00+03:00
playwright_root: /tmp/demo-playwright
---

## Cases

### tc-1-1
title: Widget visible
channel_class: ui
map_status: mapped
path: tests/demo/test_widget.py
nodeid: tests/demo/test_widget.py::test_widget_visible

### tc-1-2
title: API list
channel_class: api
map_status: out_of_scope
reason: api

### tc-1-3
title: Orphan old
channel_class: ui
map_status: out_of_scope
reason: orphan

### tc-1-4
title: Scrollbar appearance
channel_class: ui
map_status: missing
reason: pure visual; no stable locator

## Gaps

- tc-1-4 left missing (visual scrollbar); e2e-run.md not written until all UI-active cases are bound or explicitly missing with reason.
- For Virtuoso lists in real suites, see playwright root `.cursor/reference/virtuoso-scroll.md`; document pointer here, not the algorithm.

Did not write to Upservice or Testmo.
