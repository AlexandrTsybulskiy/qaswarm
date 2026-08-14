---
slug: task-1
title: Show sprint dates
product: demo
task_id: 1
testdoc: task-1
status: ready
fetched_at: 2026-08-14T12:00:00+03:00
source: mixed
---

## Summary

pass: 1
fail: 1
blocked: 0
skipped: 2
smoke_gate: yes

## Results

### tc-1-1
verdict: fail
channel: browser
observed: Settings screen missing Menu item
reason: expected not matched

### tc-1-2
verdict: pass
channel: http
observed: 200 GET /v1/sprints

### tc-1-3
verdict: skipped
channel: none
observed:
reason: smoke-gate

### tc-1-4
verdict: skipped
channel: none
observed:
reason: smoke-gate

## Gaps

- none

Did not write to Upservice or Testmo.
