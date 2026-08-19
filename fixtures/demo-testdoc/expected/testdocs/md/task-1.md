---
slug: task-1
title: Показать даты спринта
product: demo
task_id: 1
requirement: task-1
status: ready
fetched_at: 2026-08-14T09:00:00+03:00
next_id: 5
---

## Cases

### tc-1-1
title: Даты спринта видны
action: Открыть карточку спринта
expected: видны даты начала и окончания
status: active

### tc-1-3
title: Сохранение сохраняет даты
action: Нажать сохранить
expected: даты сохраняются
status: active

### tc-1-4
title: Плейсхолдер без дат
action: Открыть спринт без дат
expected: показан плейсхолдер
status: active

### tc-1-2
title: Скрыты
action: Открыть спринт без дат
expected: строка дат скрыта
status: orphan

## Checklist

- tc-1-1
- tc-1-3
- tc-1-4

## Gaps

- none

Did not write to Upservice or Testmo.
