---
name: generate-testdocs
description: Builds atomic test cases in git from a ready requirement card. Use when the user says сделай тест-доки, тест-кейсы для задачи, or сгенерируй кейсы. Does not write to Upservice or Testmo.
---

# generate-testdocs

## Steps

1. Resolve the single product id (v1: `upservice` if that is the only folder). If `raw/_incoming/` is not empty, stop.
2. Find `memory/<id>/requirements/<slug>.md` (ticket id → `task-<id>`). If missing or `status` is not `ready`, stop. Tell the user to run `analyze-requirement` first. Do not start specifier, hunter, or invent Testable text.
3. Launch `specifier` with `mode: testdocs`, the requirement path, and the **Atomic cases** rules below. If the Task harness has no `specifier` type, use `generalPurpose` instructed to follow `.cursor/agents/specifier.md` verbatim with `mode: testdocs`. Specifier writes `_incoming/testdocs.md` without case ids. Case `title` must match the language of `action`/`expected` (Russian for Upservice Testable). No Figma, no product API, no Testmo.
4. After MANIFEST lists `testdocs.md`, launch `librarian` with goal `testdoc`. Librarian runs `tools/testdoc_merge.py` (writes `testdocs/md/<slug>.md`) then `tools/testdoc_csv.py` (writes `testdocs/csv/<slug>.csv`).
5. Report the suite path, CSV path, active count, orphan count, and gaps. Say testdocs are ready only if both files exist and `py -3 tools/memory_schema.py memory/<id>` would pass.
6. Never write to Upservice or Testmo. Do not use browser MCP or Figma MCP.

## Atomic cases

**Один кейс = одна проверка.** Если в `expected` (или в `action`) несколько независимых проверок — разбить на отдельные кейсы. Не оставлять «umbrella» кейсы, где один `expected` перечисляет несколько типов, полей, представлений или эффектов.

### Когда разбивать

Сигналы составного пункта Testable:

- список через запятую, `/`, «и», «а также»;
- несколько типов сущностей, полей UI, представлений, платформ;
- два разных эффекта в одном `expected` (например «оранжевый стиль Upservice **и** другой стиль Google»).

### Как разбивать

1. Взять пункт `## Testable` как источник; при разбиении **не выдумывать** проверки вне требования.
2. Для каждой вариации — отдельный `### case`: свой `title`, `action`, `expected`.
3. `title` — короткая подпись на том же языке, что шаги (русский для Upservice); не дублировать полный `expected`.
4. В `action` явно зафиксировать **предусловие вариации** (конкретный тип события, представление, поле карточки).
5. В `expected` — **одна** проверка для этой вариации.
6. Простой пункт Testable с одной проверкой — один кейс; `action`/`expected` копировать дословно (реж по **первой** `→` / `->`).

### Паттерны (примеры)

| Составной Testable | Атомарные кейсы |
|---|---|
| «видны Event, Out of office, Focus time, Working location (и при наличии — Task, Appointment schedule)» | один кейс на каждый тип: предусловие «в аккаунте есть событие типа X» → «в сетке видно событие типа X» |
| «переключить День / Неделя / Месяц → события видимы» | три кейса: «День», «Неделя», «Месяц» |
| «на карточке: название, время, тип/источник» | три кейса: название; время или «весь день»; тип/источник |
| «типы различимы по стилю/метке» | один кейс на каждый спецтип |
| «события типов X/Y/Z не создают задачи» | один кейс на каждый тип |
| «Upservice оранжевый; Google другой стиль и без аватара» | два кейса: стиль Upservice; стиль Google и отсутствие аватара |

### Ревизия сьюта

Если сьют уже есть и пользователь просит атомарность (или координатор видит составные кейсы): specifier пишет **полный** incoming со всеми атомарными кейсами; librarian merge с `--existing` — старые составные id становятся `orphan`, новые получают новые id. В checklist только `active`.

### Не разбивать без нужды

Один сценарий с одним логическим исходом оставить одним кейсом (например «события из дополнительного календаря отображаются», «клик открывает read-only», «синхронизация не ломается»).

### Формат incoming

См. `fixtures/demo-testdoc/incoming/testdocs.md`: `### case` без `tc-…` id; поля `title`, `action`, `expected` only; затем `## Gaps`.
