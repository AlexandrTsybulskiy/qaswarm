# QA Swarm — проверка через MCP

Дата: 2026-08-14  
Статус: черновик на ревью  
Область: подпроект 4. Опирается на ядро и память, анализ требований и тест-документацию (`docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md`, `docs/superpowers/specs/2026-08-13-qa-swarm-requirements-analysis-design.md`, `docs/superpowers/specs/2026-08-14-qa-swarm-test-documentation-design.md`). Не заменяет их.

## 1. Зачем

Нужно из готового сюита testdocs получить **канонический прогон** в git-памяти: по каждому `active` кейсу живой вердикт из browser MCP или HTTP API. Следующие контуры (тикеты, e2e, TMS) читают файлы, а не чат.

Канон — git. В Upservice и в Testmo этот контур не пишет. Playwright не генерирует.

## 2. Цели v1

- Команда «проверь сюит &lt;id&gt;» даёт канонический прогон в `memory/upservice/runs/`.
- Вход: только `testdocs/<slug>.md` хотя бы с одним кейсом `active`. Иначе стоп, generate-testdocs сам не запускается.
- Одна команда — один сюит. `orphan` не гоняем.
- Канал по кейсу: UI → browser MCP, API → HTTP; неясно или канал недоступен → `blocked`, не `fail`.
- Smoke: опциональный `tier: smoke` на кейсе testdocs. Все smoke сначала; любой не `pass` → остальные `skipped`. Нет smoke — весь сюит без ворот. После прошедших smoke обычный `fail` сюит не стопает.
- Строка результата: вердикт, канал, короткий `observed`, `reason` если не `pass`. Скриншотов в git нет.
- Агенты не пишут в Upservice и не вызывают Testmo.

Критерий готовности: три сценария в разделе 11 проходят; `tools/memory_schema.py memory/upservice` возвращает `OK`.

## 3. Вне скоупа v1

- Запись в Testmo / иной TMS.
- Запись в задачу Upservice.
- Playwright / e2e (контур 6), верификация багов (контур 7), тикетный процесс (контур 5).
- Figma MCP.
- Мобильный MCP (нативный iOS/Android без веба → `blocked`).
- Пакетный прогон всех сюитов / подмножество id в команде.
- История прогонов отдельными файлами (git хранит прошлое; канон — последний overwrite).
- Скриншоты, HAR, вложения в `raw/`.
- Автозапуск `generate-testdocs` или `analyze-requirement` из этого skill.
- Автопометка testdocs `stale` после прогона; автопроставление `tier: smoke` Scribe.

## 4. Зафиксированные решения

| Тема | Решение |
|------|---------|
| Куда писать | Только git: `runs/<slug>.md`; testdocs не меняем, кроме опционального `tier` |
| Вход | Сюит testdocs с `active`; иначе стоп |
| Гранулярность команды | Один сюит за команду |
| Канал | По тексту `action`/`expected`; UI → browser, API → HTTP |
| Непригодный канал | `blocked`, не `fail` |
| Повтор | Overwrite того же `runs/<slug>.md` |
| Smoke | `tier: smoke`; гейт если любой smoke не `pass` |
| После гейта | Незапущенные = `skipped`, не `blocked` |
| После прошедшего smoke | Все остальные `active`; `fail` не стопает |
| Доказательство | Текст `observed` + `reason`; без скриншотов |
| Кто исполняет | Субагент Verifier → `_incoming/run.md` |
| Кто пишет канон | Librarian; вердикты не пересчитывает |
| Python | Схема `runs/` + сохранение `tier` при merge testdocs; без merge id прогона |
| Роли | Координатор + Verifier + Librarian |

## 5. Архитектура

Человек говорит с координатором. Skill: `verify-testdocs`.

```text
человек → координатор
       → [нет testdocs/<slug>.md или нет active] стоп, сначала generate-testdocs
       → [непустой _incoming/] стоп
       → Verifier → _incoming/run.md + MANIFEST
       → Librarian → runs/<slug>.md + runs/index.md
       → человек (путь, pass/fail/blocked/skipped, сработал ли smoke-гейт)
```

Границы:

- Verifier читает канон testdocs и `products/<id>/config.yaml`. Ходит в browser MCP и/или HTTP. Не пишет `runs/`, testdocs, тикеты. Не вызывает Figma, Testmo, Upservice write.
- Librarian не ходит в продукт и MCP. Overwrite канона, редакция секретов, схема. Вердикты из incoming не пересчитывает. Проверяет, что набор id = все `active` сюита.
- Координатор не пишет `memory/`.
- Hunter, Analyst, Scribe в этом контуре не запускаются.

Замок ядра: непустой `memory/<product-id>/raw/_incoming/` — новый проход нельзя.

## 6. Пути и slug

```text
memory/upservice/runs/index.md
memory/upservice/runs/<slug>.md
```

`<slug>` совпадает со slug сюита testdocs.

- Один сюит — один файл прогона. Повтор — overwrite, не `task-1842-2`.
- `runs/` может отсутствовать: дерево ядра, `requirements/` и `testdocs/` остаются валидными.
- `runs/index.md` не валидируется как карточка прогона. Таблица: Slug, Testdoc, Pass, Fail, Blocked, Skipped, Source, Card.

Черновик Verifier: `memory/upservice/raw/_incoming/run.md` плюс `MANIFEST.md` (список содержит `run.md`). После успеха Librarian удаляет incoming.

Карточки `runs/` — не entity-карточки ядра. Поле `source` на прогоне — своё (раздел 7), не enum `public` \| `internal` \| `browser` из `memory-card.mdc`.

## 7. Контракт testdocs (расширение) и прогона

### 7.1. `tier` на кейсе testdocs

В секции кейса опционально:

- `tier: smoke`

Нет поля — обычный кейс. Иное значение, чем `smoke`, — ошибка схемы.

Scribe в v1 `tier` не ставит и не угадывает. Человек (или явная правка файла) может пометить smoke. Повтор `generate-testdocs` **не должен сбрасывать** `tier`: хелпер merge testdocs сохраняет `tier` существующего кейса при совпадении ключа `action`+`expected`; incoming без `tier` поле не очищает; incoming с `tier` обновляет; новый кейс без `tier` остаётся без поля.

Нет ни одного `tier: smoke` среди `active` — прогон без ворот, все `active` в порядке чек-листа.

### 7.2. Файл прогона

YAML frontmatter, парсер ядра: одна строка `ключ: значение`.

Обязательные поля:

- `slug` — как у testdocs, `[a-z0-9-]+`, совпадает с именем файла
- `title` — как у testdocs
- `product` — `upservice` в v1
- `task_id` — id или `none`
- `testdoc` — slug сюита, тот же что `slug` в v1
- `status` — `ready` (полный прогон: по строке на каждый `active` кейс сюита)
- `fetched_at` — ISO-8601 **с смещением**, время окончания прогона
- `source` — ровно одно из `browser` \| `public` \| `internal` \| `mixed` \| `none`

Как считать `source` (по факту **отправленных** запросов в этом прогоне, не по классификации кейса):

- ни одного запроса к browser MCP или HTTP (все строки `blocked`/`skipped` без вызова) → `none`
- вызывали только browser MCP → `browser`
- вызывали только public HTTP → `public`
- вызывали только internal HTTP → `internal`
- вызывали больше одного из {browser, public, internal} → `mixed`

Классификация кейса и `channel` в строке — не то же самое, что `source` файла.

`status: ready` только если incoming содержит ровно множество id всех `active` кейсов сюита. Иначе Librarian канон не пишет.

Тело:

1. `## Summary` — целые счётчики: `pass`, `fail`, `blocked`, `skipped`, флаг `smoke_gate: yes` \| `no`
2. `## Results` — секции `### tc-<prefix>-<n>` в порядке исполнения: сначала все smoke `active` (порядок чек-листа среди них), затем остальные `active` (порядок чек-листа среди них). В каждой, строки `ключ: значение`:
   - `verdict` — `pass` \| `fail` \| `blocked` \| `skipped`
   - `channel` — `browser` \| `http` \| `none`
   - `observed` — короткая цитата UI или HTTP status/фрагмент тела; у `skipped` допускается пустое значение
   - `reason` — обязательно, если `verdict` не `pass`; иначе поле можно опустить
3. `## Gaps` — заголовок обязателен; пустая секция допустима (`- none`)
4. Явная строка: в Upservice и Testmo не писали

Секреты не копировать. Скриншотов и бинарников нет.

Вердикты:

- `pass` — `observed` соответствует `expected`
- `fail` — канал отработал, `observed` не соответствует `expected`
- `blocked` — этот кейс не удалось исполнить (нет канала, не веб, нет URL, 401, нет MCP, падение MCP на этом шаге, логин недоступен)
- `skipped` — кейс не запускали **только** из‑за smoke-gate

`channel: none` только вместе с `blocked` или `skipped`.

### 7.3. Incoming

Frontmatter: `slug`, `title`, `product`, `task_id`, `testdoc`, `fetched_at`, `source`. Без выдуманного `status` — Librarian ставит `ready` после проверки полноты.

Verifier пишет секции результатов **с id** из testdocs. Librarian не пересчитывает `verdict`. Неполный набор id, лишний id, `orphan` в результатах — канон не писать, incoming не считать успехом.

## 8. Роли и skill

### Координатор

Проверяет замок `_incoming/` и наличие testdocs с `active`. Запускает Verifier, затем Librarian. Ответ: путь прогона, счётчики, `smoke_gate`, gap. Не пишет `memory/`. Не запускает Hunter / Analyst / Scribe / generate-testdocs из этого skill.

### Verifier (новое)

Субагент `verifier`. Читает только канон `testdocs/<slug>.md` и конфиг продукта.

Классификация (по `action` и `expected`, без поля канала в testdocs):

- UI (экран, тап, меню, drag, iOS/Android/веб-страница) → browser
- API (метод, путь, ресурс каталога, JSON) → HTTP
- сомнение → этот кейс `blocked`, `channel: none`, `reason` про классификацию

HTTP: public, затем internal, если internal есть в конфиге и public не дал ответа на этот кейс. Browser не запасной канал для API. HTTP не запасной канал для UI.

Browser MCP только если `mcp.browser` истинно и задан `ui.base_url`. Иначе UI-кейсы `blocked`. Хост не угадывать. Учётные данные не выдумывать и в git не писать: нет сессии — `blocked`.

Нативный iOS/Android при наличии только browser MCP → `blocked` (не веб).

Порядок исполнения:

1. Все `active` с `tier: smoke`, в порядке чек-листа. Один не `pass` не отменяет остальные smoke.
2. Если среди smoke есть не `pass` — каждый оставшийся не-smoke `active` → `skipped`, `reason: smoke-gate`, без вызова MCP/HTTP. `smoke_gate: yes`.
3. Если все smoke `pass` (или smoke не было) — остальные `active` до конца. `fail` и `blocked` на них не стопают сюит. `smoke_gate: no`.

Падение MCP посреди сюита: уже записанные вердикты сохранить; текущий кейс `blocked`; дальше те же правила (добить smoke, затем гейт или остаток). Если MCP дальше недоступен, не-smoke получают `blocked`, не `skipped`.

Пишет только `_incoming/run.md` и участие в `MANIFEST.md`.

### Librarian

Расширение: канонизирует `run.md` в `runs/`. Дедуп по slug (overwrite). Не затирает чужие прогоны. После записи — `python`/`py -3 tools/memory_schema.py memory/upservice`. Редакция секретов в `observed`/`reason`/`gaps`.

Расширение merge testdocs: сохранять `tier` (раздел 7.1).

### Skill `verify-testdocs`

Триггеры: «проверь сюит», «прогони кейсы», «verify testdocs».

## 9. Поток

1. Резолв продукта. Непустой `_incoming/` — стоп.
2. Найти `memory/<id>/testdocs/<slug>.md`. Нет файла или нет ни одного `active` — стоп: сказать запустить `generate-testdocs`. Verifier не стартует. Кейсы из чата не брать.
3. Verifier: сюит + конфиг → incoming со всеми `active` id.
4. Librarian: полнота id, секреты, overwrite `runs/<slug>.md`, строка в `runs/index.md`, схема.
5. Координатор отчитывается. «Прогон готов» только если файл есть и схема `OK`.

Спека без тикета: тот же поток, `task_id: none`, id вида `tc-<slug>-<n>`.

## 10. Ошибки

| Ситуация | Поведение |
|----------|-----------|
| Нет сюита testdocs или нет `active` | Стоп, не выдумывать кейсы |
| Нет MANIFEST / нет `run.md` | Канон runs не писать |
| Incoming id ≠ множество `active` | Канон не писать |
| Нет `ui.base_url` или `mcp.browser: false` | UI-кейсы `blocked`; если они smoke — гейт |
| HTTP 401 / нет токена | API-кейсы `blocked`, не `fail` |
| Нативный экран, только browser MCP | `blocked` |
| `expected` не совпало с `observed` | `fail` |
| MCP упал на кейсе | Этот кейс `blocked`; дальше по §8 |
| Секрет в `observed` | Не копировать / вырезать |
| Повтор того же slug | Тот же файл, overwrite |
| Testmo / Upservice write | Не вызываем, не пишем |

## 11. Проверка

Фикстура `fixtures/demo-run/`: incoming с вердиктами (smoke не `pass` + хвост `skipped`, смесь каналов, `source: mixed` или `none`), ожидаемый канон. Сверка формы, id, вердиктов, счётчиков, не живого MCP.

`tools/memory_schema.py` проверяет `runs/*.md`, если папка есть. Отсутствие папки — не ошибка. `index.md` как карточка прогона не проверяется.

Опциональный `tier: smoke` на testdocs не ломает сюиты без поля. Merge testdocs сохраняет `tier`.

**Сценарий 1 — сюит → прогон**  
Цель: все `active` получают вердикт.  
Шаги: команда на задачу с `testdocs/task-<id>.md` и хотя бы одним исполняемым каналом.  
Ожидание: `runs/task-<id>.md`, по строке на каждый `active`, схема `OK`; Upservice и Testmo не вызваны.

**Сценарий 2 — нет сюита**  
Цель: контуры не сливаются.  
Шаги: команда без testdocs / без `active`.  
Ожидание: стоп, `_incoming` пуст, файлов runs не появилось.

**Сценарий 3 — smoke-гейт и повтор**  
Цель: гейт и overwrite.  
Шаги: сюит с `tier: smoke`; хотя бы один smoke не `pass`; затем повтор той же команды с другим `observed`.  
Ожидание: smoke в файле с вердиктами; не-smoke `skipped` и `reason: smoke-gate`; повтор — тот же путь, содержимое заменено, второго файла нет.

Прогон: `py -3 tools/memory_schema.py memory/upservice` → `OK`.

Живой browser MCP на приёмке схемы не обязателен: сценарий 1 в автотестах закрывается фикстурой incoming. Ручной прогон на `task-5210629` после реализации честно даст `blocked`/`skipped`, пока нет веба/`ui.base_url` и пока кейсы нативные.

## 12. Конфиг продукта

Новое необязательное поле: `ui.base_url` — база веб-UI. Нет поля — UI-кейсы `blocked`.

`mcp.browser` как в ядре: для этого контура browser MCP разрешён только при `true`. Для `index-system` правило ядра не меняется (browser по-прежнему запрещён на карте).

Verifier не угадывает URL и не берёт Figma file URL как UI.

## 13. Реализация (после утверждения spec)

- `.cursor/agents/verifier.md`
- `.cursor/skills/verify-testdocs/SKILL.md`
- Дополнить Librarian и координатора (`runs/`, goal `run`, не писать в Upservice/Testmo)
- Расширить `tools/memory_schema.py` (валидация прогона + опциональный `tier`) и `tools/testdoc_merge.py` (сохранение `tier`) + тесты
- `fixtures/demo-run/`
- Пример `docs/examples/product-config.yaml`: закомментированный `ui.base_url`
- Строка в `AGENTS.md` / `README.md`

Отдельный сервис, Playwright, клиент Testmo и запись в Upservice не нужны.

## 14. Что сознательно отложено

- Поле `channel` на кейсе testdocs.
- История прогонов (`runs/<slug>/<timestamp>.md`).
- Подмножество id в команде и прогон всех сюитов.
- Скриншоты как доказательство.
- Мобильный MCP.
- Авто-smoke из Scribe.
- Пометка прогона `stale`, когда testdocs изменились.
