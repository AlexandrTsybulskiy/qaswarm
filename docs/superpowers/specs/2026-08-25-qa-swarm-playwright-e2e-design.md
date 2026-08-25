# QA Swarm — Playwright / e2e (контур 6)

Дата: 2026-08-25  
Статус: черновик на ревью  
Область: подпроект 6 (Playwright / e2e). Опирается на ядро и память, анализ требований, тест-документацию и MCP-проверку (`docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md`, `docs/superpowers/specs/2026-08-13-qa-swarm-requirements-analysis-design.md`, `docs/superpowers/specs/2026-08-14-qa-swarm-test-documentation-design.md`, `docs/superpowers/specs/2026-08-14-qa-swarm-mcp-verification-design.md`). Не заменяет их. Контур 5 (тикеты) не блокирует этот подпроект.

## 1. Зачем

Нужно из готового сюита `testdocs` с UI-кейсами получить **автотесты в существующем Playwright-репозитории продукта**, прогнать их и сохранить в git-памяти qaswarm **канон маппинга** (кейс ↔ тест) и **канон вердикта прогона**. Следующие контуры (тикеты, верификация багов, TMS) читают файлы, а не чат.

Канон оркестрации и вердиктов — git в `qaswarm`. Код тестов — во внешнем Playwright-репо. В Upservice и в Testmo этот контур не пишет. MCP-прогон (`runs/`) не перезаписывает и не подменяет.

## 2. Цели v1

- Команда «сделай e2e для &lt;id/slug&gt;» (и аналоги) даёт: актуальный маппинг в `memory/<id>/e2e/`, при необходимости новые/дописанные UI-тесты во внешнем репо, прогон pytest и вердикт в `memory/<id>/e2e-runs/`.
- Вход: только `testdocs/md/<slug>.md` хотя бы с одним `active` UI-кейсом. Иначе стоп; `generate-testdocs` сам не запускается.
- Одна команда — один сюит. `orphan` не автоматизируем и не гоняем.
- Гибрид: сканируем существующие тесты по маркеру `tc-id`; Writer пишет только `missing` UI-кейсы, в стиле conventions Playwright-репо.
- Связь кейс↔тест: маркер в коде теста (источник правды) + зеркало в `e2e/<slug>.md`.
- API-кейсы testdocs: `out_of_scope` в маппинге; в `e2e-runs` строк на них нет.
- Если после Writer остались UI-`active` в статусе `missing` — канон прогона не пишем (map может остаться `draft`).
- Агенты не пишут в Upservice и не вызывают Testmo. Не трогают `runs/` контура 4.

Критерий готовности: три сценария в разделе 11 проходят; `tools/memory_schema.py memory/upservice` возвращает `OK` при наличии деревьев `e2e/` / `e2e-runs/`.

## 3. Вне скоупа v1

- Тикетный процесс (контур 5), верификация багов (контур 7).
- Запись в Testmo / Upservice.
- Перенос Playwright suite внутрь `qaswarm`.
- Автоматизация API-кейсов testdocs в этом контуре (даже если в Playwright-репо есть API-тесты).
- Пакетный прогон всех сюитов / подмножество case id в команде.
- История прогонов отдельными файлами (канон — последний overwrite `e2e-runs/<slug>.md`).
- Скриншоты, traces, HAR в git qaswarm (остаются в Playwright-репо / локально, в memory не копируем).
- Автозапуск `generate-testdocs`, `analyze-requirement` или `verify-testdocs` из этого skill.
- Подмена или merge с MCP `runs/`.
- CI продукта Upservice как часть skill (человек/GitLab могут гонять те же файлы отдельно).

## 4. Зафиксированные решения

| Тема | Решение |
|------|---------|
| Результат v1 | Генерация недостающего + прогон + канон в memory |
| Где код | Внешний Playwright-репо; путь в `products/<id>/config.yaml` |
| Режим | Гибрид: map существующих, писать только missing UI |
| Какие кейсы | Только UI-`active`; API → `out_of_scope` |
| Вердикт | `e2e-runs/<slug>.md`, не `runs/` |
| Маппинг | Маркер в тесте + зеркало `e2e/<slug>.md` |
| Источник правды связи | Маркер в Playwright-репо; memory — зеркало после скана/записи |
| Вход | `testdocs/md/<slug>.md` с UI-`active`; иначе стоп |
| Гранулярность | Один сюит за команду |
| Missing после Writer | Стоп до run; run-канон не писать |
| API в e2e-runs | Нет строк |
| Роли | Координатор + e2e-builder (scan/write/run) + Librarian |
| Upservice / Testmo | Не вызываем, не пишем |
| Контур 4 | Не вызываем, `runs/` не меняем |

## 5. Архитектура

Человек говорит с координатором. Skill: `generate-e2e`.

```text
человек → координатор
       → [нет testdocs / нет UI-active] стоп → generate-testdocs
       → [непустой raw/_incoming/] стоп
       → [нет playwright.root] стоп
       → e2e-builder:
            scan маркеров в Playwright-репо
            classify UI | API | unclear
            write missing UI (conventions репо + маркер tc-id)
            [если UI-active ещё missing] → incoming только e2e.md (draft), run нет
            иначе pytest по nodeid → incoming e2e.md + e2e-run.md + MANIFEST
       → Librarian → e2e/<slug>.md (+ index) и при полном run → e2e-runs/<slug>.md (+ index)
       → человек (пути, written/missing, pass/fail/blocked/skipped)
```

Границы:

- `e2e-builder` читает канон testdocs и конфиг продукта; пишет код только в `playwright.root`; в qaswarm пишет только `_incoming/` (+ участие в MANIFEST). Не пишет канон `memory/`, не вызывает Upservice/Testmo, не трогает `runs/`.
- Librarian не ходит в продукт и не гоняет pytest. Пишет канон, редактирует секреты, гоняет схему. Вердикты и nodeid из incoming не пересчитывает; проверяет контракты полноты (раздел 7).
- Координатор не пишет канон `memory/`.
- Hunter, Analyst, Scribe, Verifier в этом skill не запускаются.

Замок ядра: непустой `memory/<product-id>/raw/_incoming/` — новый проход нельзя.

Один субагент `e2e-builder` в v1 закрывает scan + write + run (можно позже разрезать без смены контрактов файлов).

## 6. Пути и slug

```text
memory/<product-id>/e2e/index.md
memory/<product-id>/e2e/<slug>.md
memory/<product-id>/e2e-runs/index.md
memory/<product-id>/e2e-runs/<slug>.md
```

`<slug>` совпадает со slug сюита testdocs (`task-<id>` или slug спеки без тикета).

- Один сюит — один файл маппинга и один файл прогона. Повтор — merge/overwrite тех же путей, не `task-1842-2`.
- `e2e/` и `e2e-runs/` могут отсутствовать: дерево ядра, `requirements/`, `testdocs/`, `runs/` остаются валидными.
- `e2e/index.md` и `e2e-runs/index.md` не валидируются как карточки. Таблицы-индексы (Slug, Testdoc, …, Card).

Черновики: `memory/<product-id>/raw/_incoming/e2e.md` и при прогоне ещё `e2e-run.md`; `MANIFEST.md` перечисляет написанные файлы. После успеха Librarian удаляет incoming.

Код тестов и PO — только под `playwright.root` (вне дерева `memory/`).

## 7. Контракты

### 7.1. Маркер в Playwright-репо

Источник правды связи:

```python
@pytest.mark.qaswarm_tc("tc-5204373-1")
```

- Имя маркера: `qaswarm_tc`.
- Значение: ровно id кейса testdocs (`tc-<prefix>-<n>`).
- Один маркер на один тест; один `tc-id` не должен висеть на двух nodeid (дубликат → стоп / gap, не угадывать).
- Регистрация маркера в Playwright-репо — часть внедрения (pytest.ini / conftest); без регистрации pytest предупреждает, skill всё равно сканирует исходники по паттерну маркера.

Скан: обход `tests/**/*.py` под `playwright.root`, извлечение `(tc-id → relative path, nodeid)`.

### 7.2. Классификация кейса

По тексту `action` / `expected` (та же идея, что канал в MCP-verify):

| Класс | Правило (v1) | `map_status` |
|-------|----------------|--------------|
| `api` | Явный HTTP/API без UI | `out_of_scope` |
| `ui` | Экран, клик, поле, виджет, навигация Web | `mapped` / `missing` / `written` |
| `unclear` | Неясно | не Writer; остаётся `missing` → блокирует run, пока человек не уточнит или не пометит вне скоупа вручную в map (правка канона только через Librarian/повтор skill) |

В v1 ручная правка «forced out_of_scope» для unclear — через повторный проход после правки testdocs или явного маркера в будущем; отдельного UI для этого нет.

### 7.3. Карточка `e2e/<slug>.md`

YAML frontmatter, парсер ядра: одна строка `ключ: значение`.

Обязательные поля:

- `slug` — `[a-z0-9-]+`, совпадает с именем файла и testdocs
- `title` — как у testdocs
- `product` — `upservice` в v1
- `task_id` — id или `none`
- `testdoc` — slug сюита
- `status` — `draft` \| `ready` \| `stale`
- `fetched_at` — ISO-8601 **с смещением**
- `playwright_root` — путь из конфига на момент записи (без секретов; может быть абсолютным локальным путём машины)

`status: ready` только если каждый UI-`active` кейс сюита имеет `map_status` `mapped` или `written`. Иначе `draft`. API-`active` обязаны иметь `out_of_scope`.

Тело:

1. `## Cases` — секции `### <tc-id>` в порядке чек-листа testdocs. В каждой, строки `ключ: значение`:
   - `title` — из testdocs
   - `channel_class` — `ui` \| `api` \| `unclear`
   - `map_status` — `mapped` \| `missing` \| `written` \| `out_of_scope`
   - `path` — относительный путь от `playwright_root` (обязателен для `mapped`/`written`)
   - `nodeid` — pytest nodeid (обязателен для `mapped`/`written`)
   - `reason` — если `missing` / `out_of_scope` / `unclear`, кратко почему
2. `## Gaps` — заголовок обязателен; пустая секция допустима (`- none`)
3. Явная строка: в Upservice и Testmo не писали

`written` означает: в этом проходе Writer создал или существенно дополнил тест под кейс. Повторный скан того же маркера на следующем прогоне может отразить уже `mapped` (стабильная связь есть); оба значения допустимы для `ready`.

### 7.4. Карточка `e2e-runs/<slug>.md`

Обязательные поля frontmatter:

- `slug`, `title`, `product`, `task_id`, `testdoc` — как у e2e/testdocs
- `status` — `ready` (полный прогон UI-набора, см. ниже)
- `fetched_at` — ISO-8601 с смещением, конец прогона
- `source` — всегда `playwright` в этом контуре
- `e2e` — slug карточки маппинга (в v1 = `slug`)

`status: ready` только если incoming содержит ровно по одной строке результата на каждый UI-`active` кейс, у которого в актуальном map `map_status` ∈ {`mapped`, `written`}. Иначе Librarian канон `e2e-runs` не пишет.

Тело:

1. `## Summary` — целые: `pass`, `fail`, `blocked`, `skipped`
2. `## Results` — секции `### <tc-id>` в порядке прогона (порядок чек-листа среди гоняемых UI). В каждой:
   - `verdict` — `pass` \| `fail` \| `blocked` \| `skipped`
   - `nodeid` — как запускали
   - `observed` — короткий фрагмент вывода pytest / assertion; у `skipped` допускается пусто
   - `reason` — обязательно, если `verdict` не `pass`
3. `## Gaps` — обязателен; `- none` допустим
4. Явная строка: в Upservice и Testmo не писали; MCP `runs/` не меняли

Вердикты:

- `pass` — pytest по nodeid зелёный, исход соответствует ожиданию кейса на уровне автотеста
- `fail` — pytest красный (assertion / явный fail теста)
- `blocked` — не удалось исполнить (нет env, сломан nodeid, коллекция pytest не нашла тест, таймаут инфраструктуры)
- `skipped` — pytest skipped или кейс осознанно не стартовали внутри выбранного набора (редко в v1; не путать с API `out_of_scope`, которых в run нет)

Секреты в `observed` не копировать. Скриншотов и бинарников в memory нет.

### 7.5. Incoming

- `_incoming/e2e.md` — черновик маппинга (обязателен при любом успешном завершении builder до Librarian).
- `_incoming/e2e-run.md` — черновик прогона (только если все UI-`active` закрыты map и pytest был запущен).
- `MANIFEST.md` перечисляет файлы.

Если run не запускался (остались missing) — MANIFEST содержит только `e2e.md`; Librarian пишет `e2e/` со `status: draft` и **не** создаёт/не обновляет `e2e-runs/<slug>.md`.

## 8. Python и схема

Расширить `tools/memory_schema.py`:

- Если есть `e2e/` (кроме index) — валидировать карточки маппинга по §7.3.
- Если есть `e2e-runs/` (кроме index) — валидировать прогоны по §7.4; для `ready` проверить согласованность набора UI id с `e2e/<slug>.md` при его наличии.
- Отсутствие папок — не ошибка.
- `index.md` как карточки не проверяются.

Опционально (план реализации): хелпер скана маркеров `tools/e2e_scan.py` (детерминированный парсинг), чтобы Librarian/тесты не зависели от LLM-скана. Builder может вызывать тот же хелпер.

Фикстура `fixtures/demo-e2e/`: sample testdocs slug, incoming `e2e.md` + `e2e-run.md`, ожидаемый канон — без живого браузера.

## 9. Skill `generate-e2e`

Триггеры: «сделай e2e», «прогони playwright», «e2e для задачи», «generate e2e».

### Поток

1. Резолв единственного product id. Непустой `_incoming/` — стоп.
2. Найти `memory/<id>/testdocs/md/<slug>.md`. Нет файла или нет ни одного UI-`active` — стоп: сказать запустить `generate-testdocs`. Кейсы из чата не брать.
3. Прочитать `playwright.root` (и опционально команду прогона) из `products/<id>/config.yaml`. Нет пути / путь не существует — стоп.
4. Запуск `e2e-builder` с путями testdocs, playwright root, slug.
5. После MANIFEST — Librarian с goal `e2e` (и `e2e-run`, если файл есть).
6. Координатор отчитывается. «E2e готов» только если `e2e/<slug>.md` со `status: ready`, `e2e-runs/<slug>.md` существует и схема `OK`. Если только draft map — явно сказать, что прогон не выполнен и что missing.

Не вызывать Testmo, Upservice write, `verify-testdocs`.

### Writer

- Пишет только UI `missing`.
- Следует skills/rules Playwright-репо (`write-ui-test`, `write-e2e-test`, page objects, fixtures, `step()`, маркеры).
- Обязан повесить `@pytest.mark.qaswarm_tc("<tc-id>")` на новый или расширенный тест.
- Не выдумывает API-кейсы и не переписывает чужие тесты без маркера «в тот же tc-id», кроме добавления маркера к однозначному существующему тесту при уверенном match (иначе оставить `missing` + gap).

### Runner

- Запускает только nodeid из map со статусом `mapped`/`written` для UI-`active`.
- Команда по умолчанию: из конфига или `python run-tests.py` / pytest внутри `playwright.root` (уточняется в implementation plan под фактический entrypoint репо).
- Парсит итог в строки `e2e-run.md`.

## 10. Ошибки

| Ситуация | Поведение |
|----------|-----------|
| Нет testdocs / нет UI-active | Стоп, не выдумывать кейсы |
| Нет / битый `playwright.root` | Стоп |
| Непустой `_incoming/` | Стоп |
| Дубликат маркера на два nodeid | Стоп / gap; канон run не писать |
| Writer не закрыл UI missing | `e2e` draft; `e2e-runs` не писать |
| Нет MANIFEST / нет `e2e.md` | Канон e2e не писать |
| Incoming run id ≠ UI mapped/written set | Канон e2e-runs не писать |
| Pytest fail | `verdict: fail` |
| Nodeid не коллекционируется | `blocked` |
| Секрет в observed | Вырезать |
| Повтор того же slug | Те же пути, merge map / overwrite run |
| Testmo / Upservice write | Не вызываем |
| Правка `runs/` | Запрещена |

## 11. Проверка

**Сценарий 1 — map + generate + run (фикстура)**  
Цель: полный цикл без живого браузера.  
Шаги: фикстура incoming с закрытыми UI map и вердиктами.  
Ожидание: канон `e2e/` `ready`, `e2e-runs/` с строками на UI id, схема `OK`.

**Сценарий 2 — нет testdocs**  
Цель: контуры не сливаются.  
Шаги: команда без сюита / без UI-active.  
Ожидание: стоп; Playwright-репо не менялось skill'ом; `_incoming` пуст; новых e2e/e2e-runs нет.

**Сценарий 3 — missing блокирует run**  
Цель: гибрид без ложного «готово».  
Шаги: map с UI `missing` после «неудачного» Writer (фикстура только `e2e.md` draft).  
Ожидание: Librarian пишет `e2e` `draft`; файла `e2e-runs/<slug>.md` нет или не обновлён; координатор не говорит «e2e готов».

Прогон схемы: `py -3 tools/memory_schema.py memory/upservice` → `OK`.

Живой прогон на реальном slug и реальном `playwright.root` — ручной после реализации; в автотестах схемы не обязателен.

## 12. Конфиг продукта

Новые поля в `products/<id>/config.yaml`:

```yaml
playwright:
  # Предпочтительно путь из env (не коммитить машинно-зависимый абсолютный путь):
  root_env: UPSERVICE_PLAYWRIGHT_ROOT
  # root: C:/path/to/upservice_playwright_testing  # локальный override, если root_env не задан
  # run_command: optional override  # иначе entrypoint Playwright-репо (run-tests.py / pytest)
```

- Рабочий корень: `playwright.root`, иначе значение env из `playwright.root_env`. Нет рабочего пути → стоп.
- Секреты (.env Playwright-репо) в qaswarm и в карточки memory не копировать.
- Пример в `docs/examples/product-config.yaml` — закомментированный блок `playwright`.

`mcp.browser` и `ui.base_url` контура 4 этим контуром не требуются (прогон идёт через pytest Playwright-репо).

## 13. Реализация (после утверждения spec)

- `.cursor/agents/e2e-builder.md` (или эквивалент Task subagent)
- `.cursor/skills/generate-e2e/SKILL.md`
- Дополнить Librarian и координатора (`e2e/`, `e2e-runs/`, goal `e2e`)
- Расширить `tools/memory_schema.py`; опционально `tools/e2e_scan.py`
- `fixtures/demo-e2e/`
- Правка `products/upservice/config.yaml` / example config
- Строка в `AGENTS.md` / `README.md`: контур 6 в Spec; уточнить «Do not do in v1» — запрещены запись тикетов и самописный e2e suite внутри qaswarm, но разрешён оркестрируемый Playwright через этот skill
- В Playwright-репо: регистрация маркера `qaswarm_tc` (минимальный PR/правка там же, вне канона qaswarm memory)

Отдельный сервис и запись в Upservice/Testmo не нужны.

## 14. Что сознательно отложено

- Контур 5 (тикеты) и 7 (верификация багов).
- Автоматизация API-кейсов testdocs через pytest API того же репо.
- Подмножество case id / пакетный прогон.
- История `e2e-runs/<slug>/<timestamp>.md`.
- Принудительный `out_of_scope` для unclear через UI команды.
- Синхронизация `stale`, когда testdocs изменились, а e2e map нет.
- Двухфазный skill «только map» / «только run».
- Зеркалирование traces/скриншотов в qaswarm.
