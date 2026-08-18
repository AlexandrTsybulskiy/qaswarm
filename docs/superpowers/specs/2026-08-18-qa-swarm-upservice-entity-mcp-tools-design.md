# QA Swarm — MCP GET/list тулы сущностей публичного API Upservice

Дата: 2026-08-18  
Статус: черновик на ревью  
Область: расширение MCP-сервера `tools/upservice_mcp/` после `docs/superpowers/specs/2026-08-18-qa-swarm-upservice-get-task-mcp-design.md`. Каталог-источник: `memory/upservice/catalog/api.md` (`fetched_at: 2026-08-13T21:51:37+03:00`, channel `public`). Не заменяет карту API, librarian и схемы `_incoming`.

## 1. Зачем

`get_task` убирает угадывание `GET /v1/tasks/{id}`. Остальные сущности карты хантер по-прежнему собирает URL сам. Нужны такие же именованные read-only тулы: GET одной записи по id (где он есть в каталоге) и GET списка коллекций.

Код personal-assistant не копируем. Write-тулы и internal API не добавляем.

## 2. Цели v1

- В том же FastMCP-сервере `upservice` есть именованные тулы из раздела 6. Каждый — только GET публичного API.
- Ответ каждого тула — `{status_code, body}` как у `get_task`. Тул файлы не пишет.
- Общий HTTP-путь: конфиг, токен, таймаут, ретрай 429, редact токена. `get_task` переводится на этот хелпер без смены внешнего контракта.
- List-тулы принимают опциональные `limit`, `offset` и `query` (фильтры каталога). Хантер не склеивает query-string сам.
- Критерий готовности: автотесты раздела 11 зелёные; существующие тесты `get_task` зелёные; `py -3 tools/memory_schema.py memory/upservice` не требуется менять (канон памяти этот контур не пишет).

## 3. Вне скоупа v1

- POST, PUT, PATCH, DELETE.
- Channels, files, external-channels и любые вложенные GET (`/attachments`, `/agreement-steps`, `/files/{id}/url`, chat messages).
- GET одной записи там, где каталог его не даёт: employees, tags.
- Генерация тулов из OpenAPI/каталога в рантайме.
- MCP на internal API.
- Нормализация ответа в `_incoming/*.json` внутри тула.
- Смена `index-system`: каталог по-прежнему через `catalog_hint` / OpenAPI, не через эти тулы.
- Запись в Upservice.
- Ретрай сети, таймаута и `status_code: 0` (только 429).
- Импорт клиента из `upservice-personal-assistant`.
- Отдельный HTTP-клиент вне `tools/upservice_mcp/`.

Пункт «остальные сущности карты» из §3 spec `get_task` этим spec снимается только для GET-by-id и list из раздела 6.

## 4. Зафиксированные решения

| Тема | Решение |
|------|---------|
| Форма тулов | Те же Cursor MCP stdio, тот же процесс `server.py` |
| Стиль | Именованные тулы, не `get_resource(resource, id)` |
| Выход | Всегда `{status_code, body}` |
| HTTP | Только GET, пути без trailing slash, как в каталоге |
| Id | Та же нормализация, что у `get_task` |
| List query | `limit` и `offset` опционально; плюс `query: object` для фильтров |
| Списки в query | Повтор параметра (`tags_ids=a&tags_ids=b`) |
| Конфликт limit/offset | Аргументы тула перекрывают одноимённые ключи в `query` |
| Кто пишет файлы | Тул — никто; хантер — только `_incoming/` |
| Продукт | Только `upservice`; иначе `status_code: 0` без запроса |
| 429 | Как у `get_task`: до 6 GET, `Retry-After` или 1→2→4→8→16 с, потолок 30 с |
| Нет тула `get_task` | Без изменений: стоп, не угадывать `/v1/tasks/{id}` |
| Нет прочего entity-тула | Не собирать его публичный URL; `index-system`/OpenAPI не стопать |
| Регистрация Cursor | Тот же `docs/examples/mcp.json` (новый сервер не нужен) |

## 5. Архитектура

```text
человек → координатор → hunter
                      → MCP get_project / list_employees / …
                      → GET {public_api.base_url}{path}[?query]
                      → {status_code, body}
                      → hunter пишет только _incoming/ (если это его задача)
```

Границы:

- MCP-сервер не пишет `memory/`, не открывает Figma, не вызывает internal URL.
- `get_task` для `kind: task` остаётся обязательным.
- Остальные entity-тулы — предпочтительный public GET этих путей. Хантер не конструирует соответствующие URL.
- `index-system` без изменений: OpenAPI и HTTP Cursor для каталога.
- Librarian / analyst / scribe / verifier эти тулы не вызывают.

## 6. Компоненты

```text
tools/upservice_mcp/
  client.py     # public_get + get_* + list_* ; get_task на public_get
  server.py     # FastMCP: тонкие обёртки всех тулов раздела 6.1
tests/test_get_task_mcp.py          # контракт get_task без регрессии
tests/test_entity_mcp.py            # новые тулы, query, URL
.cursor/agents/hunter.md            # таблица тулов; не собирать эти URL
.cursor/rules/coordinator.mdc       # нет entity-тула → mcp.json, не угадывать URL
```

HTTP по-прежнему `urllib`, без httpx и без PyYAML.

### 6.1. Набор тулов и пути

Источник путей — `memory/upservice/catalog/api.md`. Path parameter в URL — нормализованный id.

| Тул | Сигнатура MCP | GET path |
|-----|----------------|----------|
| `get_task` | `(task_id: str \| int)` | `/v1/tasks/{id}` |
| `get_project` | `(project_id: str \| int)` | `/v1/projects/{id}` |
| `get_sprint` | `(sprint_id: str \| int)` | `/v1/sprints/{id}` |
| `get_directory` | `(directory_id: str \| int)` | `/v1/directories/{id}` |
| `get_directory_record` | `(record_id: str \| int)` | `/v1/directory-records/{id}` |
| `list_tasks` | list-сигнатура | `/v1/tasks` |
| `list_projects` | list-сигнатура | `/v1/projects` |
| `list_sprints` | list-сигнатура | `/v1/sprints` |
| `list_employees` | list-сигнатура | `/v1/employees` |
| `list_tags` | list-сигнатура | `/v1/tags` |
| `list_directories` | list-сигнатура | `/v1/directories` |
| `list_directory_records` | list-сигнатура | `/v1/directory-records` |

List-сигнатура у всех list-тулов одинаковая:

```text
(limit: int | None = None, offset: int | None = None, query: dict | None = None) -> dict
```

Нет тулов: `get_employee`, `get_tag`, list/get для channels, files, external-channels.

### 6.2. Хелпер `public_get`

Клиентский вход:

```text
public_get(
  path: str,
  *,
  products_root: Path,
  query: Mapping[str, object] | None = None,
  environ=...,
  http_get=...,
  sleep=...,
  now=...,
) -> dict[str, object]
```

`path` обязан начинаться с `/v1/`, не содержать `?`, `#`, пробел и `..`. Иначе `{status_code: 0, body: {error: "invalid path"}}` без HTTP.

Сборка URL: `{base_url без /}{path}` плюс query-string, если после merge есть хотя бы один параметр. Кодирование: `urllib.parse.urlencode(..., doseq=True)`.

Конфиг, токен, Authorization, таймаут 30 с, разбор JSON, redact токена, ретрай 429 — те же правила, что у `get_task`.

`get_*` нормализует id функцией `normalize_task_id` (имя не менять; это тот же алгоритм). Пустой id или id с `/` до/после нормализации → `{status_code: 0, body: {error: "invalid …_id"}}` без HTTP. Затем `public_get("/v1/…/{id}")` без `query`.

`list_*` вызывает `merge_list_query(limit, offset, query)` и `public_get("/v1/…", query=merged)`.

### 6.3. `merge_list_query`

1. Если `query` не `None` и не `dict` → ошибка `invalid query`, HTTP нет.
2. Ключи `query`: полный матч `^[A-Za-z0-9_]+$`. Иначе `invalid query`.
3. Значение ключа: `str`, `int`, `bool`, или `list`/`tuple` таких значений. `None` в значении — ключ пропускается. Вложенные dict и прочие типы → `invalid query`.
4. `bool` в query-string: `true` / `false` (нижний регистр).
5. Элементы списка кодируются повтором ключа. Пустой список — ключ не добавляется.
6. Если `limit` не `None`: ключ `limit` в результате равен `str(limit)` (перекрывает `query["limit"]`). То же для `offset`.
7. `limit`/`offset` если заданы и не `int` (после MCP) или `< 0` → `invalid query`.
8. Пустой результат merge → запрос без `?`.

Пример: `list_projects(limit=25, query={"status": ["active", "completed"], "tags_ids": ["a", "b"]})` →

`GET {base}/v1/projects?status=active&status=completed&tags_ids=a&tags_ids=b&limit=25`

Реализация: скопировать валидный `query` в новый dict; если аргумент `limit` задан — записать ключ `limit`; то же для `offset`; затем `urlencode`. Один ключ не повторяется.

### 6.4. Обёртки FastMCP

Каждый тул в `server.py` — одна функция с docstring «Call this instead of constructing GET …». Тело: `return client.<fn>(..., products_root=REPO_ROOT / "products")`. List-тулы пробрасывают `limit`, `offset`, `query`.

## 7. Ошибки

Тул всегда возвращает `{status_code, body}`. Значение токена не в `body` и не в логах.

| Ситуация | Тул |
|----------|-----|
| 200 + JSON object | `status_code: 200`, `body` как у API |
| 200 + не-object JSON | `body` строка (как `get_task`) |
| 404 / 401 / прочие без 429 | один GET, без ретрая |
| нет токена | `401`, без HTTP |
| 429 | ретрай как `get_task` |
| сеть / таймаут | `status_code: 0` |
| нет конфига / не upservice | `status_code: 0` |
| невалидный id / path / query | `status_code: 0`, без HTTP |

Побочных эффектов нет: только GET.

## 8. 429

Полностью как в spec `get_task` §8: повтор только на HTTP 429; до 6 попыток; `Retry-After` или ряд 1, 2, 4, 8, 16 с; пауза ≤ 30 с. Хантер для любого тула из §6.1 при стойком 429 вызывает тот же тул ещё до двух раз (итого до трёх вызовов тула). 429 ≠ missing.

## 9. Роли

- Координатор: нет `get_task` — как сейчас (`docs/examples/mcp.json`, не второй Hunter, не угадывать URL). Нет другого тула из §6.1, который хантер должен был вызвать — та же подсказка mcp.json, не велеть собрать path из каталога.
- Hunter `kind: task`: без изменений, только `get_task`.
- Hunter public GET путей из §6.1: звать соответствующий тул, не собирать URL. Каталог OpenAPI для `index-system` — не эти тулы.
- Librarian, analyst, scribe, verifier — не вызывают эти тулы.

## 10. Секреты

Как в spec `get_task` §10. Имена env можно, значения нельзя. `.env` и `.cursor/mcp.json` в gitignore.

## 11. Проверка

CI не вызывает живой Upservice. HTTP мокается. Паузы 429 — подмена `sleep`.

`tests/test_get_task_mcp.py`: все текущие кейсы остаются (200, 404 один GET, 401, 429, конфиг, slash id, redact). После рефактора URL `get_task` всё ещё `{base}/v1/tasks/{id}` без query.

`tests/test_entity_mcp.py`:

1. Каждый `get_*` кроме `get_task` бьёт ровно свой path из §6.1 (проверка URL в моке).
2. Каждый `list_*` без аргументов бьёт свой path без `?`.
3. `list_projects(limit=25, offset=0, query={"status": ["active", "completed"], "tags_ids": ["a", "b"]})` → query-string содержит повтор `status` и `tags_ids` и `limit=25` и `offset=0`.
4. `query={"status": "active", "limit": 10}` плюс аргумент `limit=25` → в URL `limit=25`, не 10.
5. Ключ query `a/b` или значение dict → `status_code: 0`, HTTP не вызывается.
6. Токена нет в результате list/get.
7. `get_project("../x")` → 0 без HTTP (как slash id у task).
8. FastMCP-обёртка `get_project` прокидывает `products_root` репозитория (monkeypatch, как у `get_task`).

Ручной сценарий: reload MCP; вызвать `list_employees` и `get_project` с известным id; ответ `{status_code, body}`; файлов в `memory/` тул не создаёт.

## 12. Реализация (после утверждения spec)

- Рефактор `tools/upservice_mcp/client.py`: `public_get`, `merge_list_query`, тонкие `get_*` / `list_*`
- Обёртки в `tools/upservice_mcp/server.py`
- `tests/test_entity_mcp.py`; регрессия `tests/test_get_task_mcp.py`
- `.cursor/agents/hunter.md`, `.cursor/rules/coordinator.mdc`
- Ссылка на этот spec в `AGENTS.md` и `README.md`
- Ядро: HTTP-клиент по-прежнему только GET в `tools/upservice_mcp/` (не только `get_task`)
- Не менять `tools/memory_schema.py`, контракт `task.json`, `docs/examples/mcp.json`

Отдельный сервис, БД и запись в Upservice не нужны.
