# QA Swarm — MCP `get_task` для публичного API Upservice

Дата: 2026-08-18  
Статус: черновик на ревью  
Область: точечное расширение ядра и анализа требований. Опирается на `docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md` и `docs/superpowers/specs/2026-08-13-qa-swarm-requirements-analysis-design.md`. Не заменяет карту API, librarian и схему `task.json`.

## 1. Зачем

Хантер снимает одну задачу Upservice для `analyze-requirement`, но путь он собирает сам (`GET /v1/tasks/{id}`) через общие HTTP-тулы Cursor. Это ломается на 401 (токен не в env процесса), на угаданном URL и на 429 публичного API.

Нужен именованный тул в том же смысле, что `get_task_detailed_info` у personal-assistant: хантер вызывает `get_task(task_id)` и не разбирает, каким эндпоинтом пользоваться. Код ассистента не копируем: там внутренний API `v1/{workspace_id}/tasks/{id}/`, сессия пользователя и write-тулы.

## 2. Цели v1

- В Cursor есть MCP-тул `get_task`. Внутри — только `GET {public_api.base_url}/v1/tasks/{task_id}`.
- Ответ тула — сырой JSON API: `{status_code, body}`. Хантер по-прежнему сам пишет `_incoming/task.json`.
- Для `kind: task` хантер обязан вызвать `get_task` и не собирать публичный URL.
- 429 не считается «задачи нет»: тул ретраит, хантер при стойком 429 вызывает тул ещё раз; канон из пустого title + errors librarian не пишет (как сейчас).
- Секрет токена не попадает в git, в `body` тула и в `task.json`.

Критерий готовности: автотесты раздела 11 зелёные; ручной сценарий с известным `task_id` даёт канон `tasks/task-<id>.md` без выдуманного URL; `py -3 tools/memory_schema.py memory/upservice` → `OK`.

## 3. Вне скоупа v1

- Тулы list/search/create/update/delete и остальные сущности карты (`projects`, `sprints`, …).
- MCP на internal API.
- Нормализация ответа в форму `_incoming/task.json` внутри тула.
- Смена `index-system` / каталога OpenAPI на этот тул.
- Запись в Upservice.
- Ретрай сети, таймаута и `status_code: 0` (только 429).
- Импорт клиента из `upservice-personal-assistant`.
- Отдельный HTTP-клиент для координатора, librarian, analyst, scribe, verifier.

## 4. Зафиксированные решения

| Тема | Решение |
|------|---------|
| Форма тула | Cursor MCP stdio, не LangChain и не CLI через Shell |
| Имя тула | `get_task` |
| Вход | `task_id` (строка или число) |
| Выход | `{status_code, body}` — сырое тело публичного API |
| HTTP | Только GET, только `/v1/tasks/{task_id}` без trailing slash |
| Кто пишет файлы | Тул — никто; хантер — только `_incoming/` |
| Каталог кода | `tools/upservice_mcp/` (не top-level `mcp/`: имя столкнётся с пакетом `mcp`) |
| Конфиг | `products/upservice/config.yaml`: `public_api.base_url`, `public_api.token_env` |
| Токен | Env `UPSERVICE_PUBLIC_API_TOKEN`; если пусто — `products/upservice/.env` (gitignore) |
| Регистрация | Пример `docs/examples/mcp.json`; рабочий `.cursor/mcp.json` в gitignore |
| 429 в туле | До 6 GET; пауза `Retry-After` или 1→2→4→8→16 с, потолок паузы 30 с |
| 429 у хантера | 429 ≠ missing; ещё до 2 вызовов `get_task`; затем лестница internal / errors |
| Нет тула в MCP | Стоп, не фолбэк на угаданный `/v1/tasks/...` |
| Ядро «без HTTP-клиента» | Исключение: GET только внутри `tools/upservice_mcp/` |
| Продукт | v1 только `upservice`; иной `products/` → `status_code: 0` без запроса |

## 5. Архитектура

```text
человек → координатор → hunter (kind: task)
                      → MCP get_task(task_id)
                      → GET {public_api.base_url}/v1/tasks/{task_id}
                      → {status_code, body}
                      → hunter пишет _incoming/task.json + MANIFEST
                      → librarian → tasks/task-<id>.md
```

Границы:

- MCP-сервер не пишет `memory/`, не открывает Figma, не вызывает internal URL.
- Хантер для публичного снимка задачи не собирает путь и не подставляет base_url в HTTP Cursor.
- Если public не дал задачу (после правил 429) и в конфиге есть `internal_api.base_url` — один запасной generic HTTP на internal, как в ядре. Отдельного internal-тула нет.
- `index-system` без изменений: OpenAPI и HTTP Cursor.
- Librarian / analyst / scribe не вызывают `get_task`. Verifier в этом контуре не меняется.
- Замок `_incoming/` без изменений.

Паттерн как у personal-assistant (`task-searcher` + `get_task_detailed_info`): оркестратор не ходит в API, субагент зовёт именованный read-only тул. Реализация — Cursor MCP и публичный API, не внутренний клиент ассистента.

## 6. Компоненты

```text
tools/upservice_mcp/
  server.py     # FastMCP, регистрация get_task, точка входа stdio
  client.py     # конфиг, токен, GET, ретрай 429
docs/examples/mcp.json
.cursor/agents/hunter.md          # kind: task → get_task
docs/examples/product-config.yaml # без новых полей
```

Зависимость: пакет `mcp` в основных зависимостях `pyproject.toml` (не только `dev`). HTTP: `urllib` из stdlib, без httpx. `ruff` src уже включает `tools`.

### 6.1. Контракт `get_task`

Вход: `task_id` обязателен.

Перед запросом нормализовать id тем же правилом, что хантер: если уже `[a-z0-9-]+` — оставить; иначе lowercase, прогоны не-алфанумерики → `-`, обрезать `-` по краям. Пустой id или id с `/` → `{status_code: 0, body: {error: "..."}}` без HTTP.

Запрос:

- URL: `{base_url без завершающего /}/v1/tasks/{id}`
- Метод: GET
- Таймаут одного GET: 30 с (истечение → `status_code: 0`, без ретрая)
- Заголовок `Authorization`: голый токен без схемы `Bearer`. Если в значении уже есть префикс `Bearer `, он снимается.

Успех: `{status_code: 200, body: <parsed JSON>}`. Если тело не JSON — `body` строка, парсер не выдумывает объект.

Тул не извлекает Figma URL и не мапит поля в `task.json`.

### 6.2. Регистрация в Cursor

`docs/examples/mcp.json` без секретов, рабочая директория — корень workspace:

```json
{
  "mcpServers": {
    "upservice": {
      "command": "py",
      "args": ["-3", "tools/upservice_mcp/server.py"]
    }
  }
}
```

Человек копирует/мёржит это в локальный `.cursor/mcp.json`. Токен только в `products/upservice/.env`. Координатор при отсутствии тула у хантера говорит включить сервер по примеру, хост не угадывает.

Сервер при старте и при каждом вызове читает актуальный `config.yaml`. Значение токена: сначала `os.environ[token_env]`, иначе файл `.env` рядом с конфигом (строки `KEY=VALUE`, без экспорта в логи).

### 6.3. Хантер, `kind: task`

1. Нормализовать `task_id`. Пустой после нормализации — ничего не писать, как сейчас.
2. Если тула `get_task` нет — стоп, не собирать `/v1/tasks/...`.
3. Вызвать `get_task`. При `status_code == 429` — повторить вызов ещё до двух раз (итого до трёх вызовов тула). Каждый вызов сам делает до 6 GET.
4. `200` и JSON задачи → `_incoming/task.json` с title/fields/figma_urls из `body`, `errors: []`, `channel: public`.
5. Иначе если в конфиге есть `internal_api.base_url` — один запасной generic HTTP на internal (не MCP). Успех → `task.json` с `channel: internal`.
6. Иначе (404, 401, стойкий 429, `0`, internal тоже мимо) → пустые title/fields, `errors[]` с кодом и коротким message без секрета; MANIFEST есть; задачу не выдумывать.
7. Figma и browser на этом kind запрещены.

Схема `task.json` и librarian без изменений: пустой title + непустой `errors` → канон `tasks/` не писать, Analyst не стартует.

## 7. Ошибки

Тул всегда возвращает `{status_code, body}`: без исключения, которое прячет HTTP-код. Токен не логировать и не класть в `body`.

| Ситуация | Тул | Хантер |
|----------|-----|--------|
| 200 + JSON задачи | `status_code: 200`, `body` как у API | `task.json`, `errors: []` |
| 404 | один GET, без ретрая | пустой title, `errors[]`, MANIFEST |
| 401 / нет токена | без ретрая; в `body` нет значения токена | то же; другой публичный URL не пробовать |
| 429 | ретрай §8 | 429 ≠ missing; ещё до 2 вызовов тула; потом errors |
| Сеть / таймаут | `status_code: 0`, `body.error`; без ретрая | errors |
| Нет конфига / не `upservice` / нет `base_url` | `status_code: 0` | стоп с этой ошибкой |
| Нет MCP-тула | — | стоп; координатор указывает `docs/examples/mcp.json` |
| Internal в конфиге, public не дал задачу | тул только public | один generic HTTP на internal |
| `task.json` пустой title + errors | — | librarian канон не пишет |

Побочных эффектов нет: только GET.

## 8. 429

Повтор только на HTTP 429. 401, 404, прочие 5xx без 429, `status_code: 0` — без ретрая.

Внутри одного вызова `get_task`:

1. GET.
2. Если 429 — ждать, повторить тот же URL. Пауза: `Retry-After` (delta-seconds или HTTP-date → секунды); если нет или не разобрать — ряд 1, 2, 4, 8, 16 секунд. Одна пауза не больше 30 с.
3. Максимум 6 попыток (5 пауз). Между попытками тул не возвращает ошибку.
4. 200 на любой попытке — обычный успех.
5. Шесть 429 подряд — вернуть последний `{status_code: 429, body}`.

Хантер: если после вызова тула всё ещё 429 — вызвать `get_task` ещё до двух раз. Дальше §6.3 шаги 5–6 (internal, затем errors). Librarian канон из пустого title + errors не строит.

Худший случай: 3 вызова тула × 6 GET. Это намеренный потолок, чтобы stdio MCP не висел бесконечно.

## 9. Роли и тексты агентов

- Координатор: при провале «нет get_task» не запускать второй Hunter и не велеть хантеру угадать URL.
- Hunter: §6.3. Фраза ядра «Call APIs with Cursor HTTP/MCP tools. There is no HTTP client in this repo» для `kind: task` заменяется на: публичный снимок — только `get_task`; HTTP-клиент есть лишь внутри MCP.
- Librarian, analyst, scribe, verifier, skills `index-system` / `generate-testdocs` / `verify-testdocs` — без обязательных правок этого контура.
- `analyze-requirement`: по-прежнему Hunter при промахе/TTL, затем librarian snapshot. Меняется способ fetch, не пути файлов.

## 10. Секреты

Имена переменных можно писать в чат и в errors (`UPSERVICE_PUBLIC_API_TOKEN`). Значения — нельзя: не в `body`, не в `task.json`, не в логи сервера. `.env` и `.cursor/mcp.json` остаются в gitignore.

## 11. Проверка

CI не вызывает живой Upservice. HTTP мокается. Паузы 429 в тестах — подмена `sleep`, не реальные секунды.

Автотесты `tests/test_get_task_mcp.py` (функция клиента/тула, не рантайм Cursor):

1. 200 → `status_code` 200, `body` как у мока, токена в результате нет.
2. 404 → ровно один GET.
3. 401 и отсутствие токена → без ретрая, значения токена в ответе нет.
4. 429 затем 200 → второй GET, успех.
5. `Retry-After: 2` → запрошенный sleep ≥ 2 с.
6. шесть 429 → ровно 6 GET, итог `429`.
7. нет `config.yaml` → `status_code: 0`.
8. клиент запрашивает только GET `{base}/v1/tasks/{id}` (проверка URL в моке).

Ручной сценарий (приёмка, живой public API):

- Включить MCP из `docs/examples/mcp.json`, токен в `.env`.
- Команда проанализировать известный `task_id`.
- Хантер вызывает `get_task`, не печатает собранный публичный URL как единственный способ.
- Есть канон `memory/upservice/tasks/task-<id>.md`; схема `OK`.
- Пойманный 429 не превращается в «задачи нет» до исчерпания §8; после исчерпания — `errors[]` с 429, без выдуманного канона.

## 12. Реализация (после утверждения spec)

- `tools/upservice_mcp/client.py`, `server.py`
- `docs/examples/mcp.json`
- зависимость `mcp` в `pyproject.toml`
- `tests/test_get_task_mcp.py`
- `.cursor/agents/hunter.md`
- `.cursor/rules/coordinator.mdc` — нет тула `get_task` → сказать про `docs/examples/mcp.json`, не запускать второго Hunter и не велеть угадать URL
- `AGENTS.md` — ссылка на этот spec
- правка ядра: HTTP-клиент разрешён только как GET в `tools/upservice_mcp/`
- не менять `tools/memory_schema.py` и контракт `task.json`

Отдельный сервис, БД и запись в Upservice не нужны.
