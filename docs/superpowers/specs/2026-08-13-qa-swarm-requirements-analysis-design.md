# QA Swarm — анализ требований и дизайна

Дата: 2026-08-13  
Статус: черновик на ревью  
Область: подпроект 2. Опирается на ядро и память (`docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md`). Не заменяет ядро.

## 1. Зачем

Нужно из задачи Upservice (обычно со ссылкой на Figma) получить **тестируемые требования** в git-памяти, чтобы следующие контуры (тест-доки, проверка, e2e) не зависели от чата.

Тикет — основной вход. Отдельная текстовая спека без тикета — запасной канал, тот же пайплайн.

## 2. Цели v1

- Команда «проанализируй задачу &lt;id&gt;» даёт каноническую карточку в `memory/upservice/requirements/`.
- Входы: канон задачи (через существующего Hunter при промахе/TTL) + Figma MCP по URL из задачи.
- В Upservice агенты **не пишут**.
- Пункты проверяемые: действие + ожидаемый результат. Нет «как в макете» без конкретики.
- Нет макета или MCP не открыл файл — карточка всё равно есть, с честным пробелом, без выдуманных экранов.

Критерий готовности: три сценария в разделе 11 проходят на реальной задаче Upservice; `tools/memory_schema.py memory/upservice` возвращает `OK`.

## 3. Вне скоупа v1

- Отдельный Task Retriever (задачи грузит Hunter).
- Запись в задачу Upservice (комментарии, поля, статус).
- Пакетный анализ спринта / всех задач.
- Тест-планы, кейсы, e2e, тикетный процесс, проверка багов.
- Browser MCP.
- Разбор дизайна не из Figma (Sketch, PDF как основной путь).

## 4. Зафиксированные решения

| Тема | Решение |
|------|---------|
| Откуда требования | Задачи Upservice; в них в основном ссылки на Figma; спека без тикета — запасной путь |
| Куда писать | Только git-память, не продукт |
| Дизайн | Figma MCP по URL из задачи |
| Роли | Координатор + Hunter (задача) + Analyst (новое) + Librarian |
| Гранулярность | Одна задача (или одна спека) за команду |
| Поиск задачи | Hunter, не отдельный субагент |

## 5. Архитектура

Человек говорит с координатором. Skill: `analyze-requirement`.

```text
человек → координатор
       → [при необходимости] Hunter → _incoming/ → Librarian (канон задачи)
       → Analyst (читает канон + Figma MCP) → _incoming/requirement.md
       → Librarian → requirements/task-<id>.md + requirements/index.md
       → человек (путь, число пунктов, пробелы)
```

Границы:

- Analyst не вызывает Upservice API и не пишет канон.
- Hunter не открывает Figma и не формулирует требования.
- Librarian не ходит в продукт и не в Figma; только черновик → канон.
- Координатор не пишет `memory/`.

Замок ядра: непустой `memory/upservice/raw/_incoming/` — новый проход нельзя.

## 6. Пути и slug

```text
memory/upservice/tasks/task-<id>.md
memory/upservice/requirements/index.md
memory/upservice/requirements/task-<id>.md
```

`entities/tasks.md` не заменяем и не превращаем в список всех задач. Снимок одной задачи — отдельный файл `tasks/task-<id>.md` (пишет Librarian после Hunter). Frontmatter снимка как у entity-карточки ядра (`slug`, `title`, `status`, `source`, `fetched_at`, `product`) плюс `task_id`. Тело: поля и ссылки, которые вернул API (включая Figma-URL, если они там есть). Без снимка Analyst не стартует.

- Есть `task_id`: slug строго `task-<id>`, где `<id>` — id задачи в Upservice, нормализованный в `[a-z0-9-]+` (цифровой id остаётся как есть: `task-1842`).
- Спека без тикета: slug от имени файла/заголовка (`[a-z0-9-]+`), `task_id: none`.
- Один смысл — один файл. Повторный анализ того же id — merge в тот же slug, не `task-1842-2`.

Черновик Analyst: `memory/upservice/raw/_incoming/requirement.md` плюс `MANIFEST.md` (как в ядре). После успеха Librarian удаляет incoming.

## 7. Контракт карточки требования

YAML frontmatter, те же ограничения парсера ядра: одна строка `ключ: значение` (списки — через запятую).

Обязательные поля:

- `slug`
- `title`
- `product` — `upservice` в v1
- `task_id` — id или `none`
- `status` — ровно `draft` | `ready` | `stale`
- `source_task` — `upservice` | `none`
- `source_design` — `figma` | `none`
- `fetched_at` — ISO-8601 **с смещением**
- `figma_urls` — URL через запятую или `none`
- `entities` — slug из `entities/` через запятую или `none`

`status`:

- `ready` — есть хотя бы один тестируемый пункт
- `draft` — только пробелы, проверяемых пунктов нет
- `stale` — только если явно переанализируют (Librarian перед повтором может пометить; не фоном)

Тело:

1. Кратко что меняется (1–5 предложений)
2. Заголовок `## Testable` — список пунктов: **действие → ожидаемый результат**. Пункт без ожидания невалиден для `ready`
3. `## Gaps` — нет Figma, MCP не открыл, сущность API неизвестна, UI-only
4. Явная строка: в Upservice не писали

Секреты из описания задачи не копировать (как в ядре).

Карточка без `fetched_at` / `source_design` / `task_id` невалидна. Координатор не называет требования готовыми, если схема не проходит.

`requirements/` может отсутствовать: дерево памяти ядра без этой папки остаётся валидным.

## 8. Роли и skill

### Координатор

Читает память, запускает Hunter только если задачи нет или TTL/`stale`, затем Analyst, затем Librarian. Ответ: путь, число пунктов, пробелы.

### Hunter

Без изменений контракта ядра. Режим точечного `recall` по задаче Upservice (id). Не пишет requirements.

### Analyst (новое)

Субагент `analyst`. Читает канон задачи и `entities/` + `catalog/api.md`. Извлекает Figma-URL. Вызывает Figma MCP только по этим URL. Не подставляет другой файл при 403. Пишет только `_incoming/requirement.md` и участие в `MANIFEST.md`.

### Librarian

Расширение: умеет канонизировать requirement-черновик в `requirements/`. Дедуп по slug. Не затирает чужие requirement-файлы. После записи — `python`/`py -3 tools/memory_schema.py memory/upservice`.

### Skill `analyze-requirement`

Триггеры: «проанализируй задачу», «разбери требования», «задача &lt;id&gt; + дизайн», приложенная спека без тикета.

## 9. Поток

1. Резолв продукта `upservice`. Пустой `_incoming/` иначе стоп.
2. Найти `memory/upservice/tasks/task-<id>.md`. Промах / TTL / stale → Hunter → Librarian (снимок задачи). Analyst не стартует раньше. Не читать `entities/tasks.md` как список инстансов.
3. Analyst: текст задачи → URL. Нет URL → `source_design: none`, пункты только из текста, gap про макет.
4. Есть URL → Figma MCP. Не открылось → gap «дизайн недоступен», экраны не выдумывать.
5. Сверка с `entities/` и каталогом. Нет сущности → gap UI-only / API неизвестен, эндпоинт не выдумывать.
6. Incoming + MANIFEST → Librarian → `requirements/task-<id>.md` + строка в `requirements/index.md`.
7. Координатор отчитывается. «Требования готовы» только если файл есть и схема `OK`.

Спека без тикета: шаг 2 пропускается (нет Hunter по задаче), `task_id: none`, `source_task: none`.

## 10. Ошибки

| Ситуация | Поведение |
|----------|-----------|
| Задачи нет в API | Стоп, не выдумывать id |
| Нет Figma-ссылки | Карточка из текста, `source_design: none` |
| Figma 403 / не тот файл | Gap, не брать соседний файл |
| Нет MANIFEST | Канон requirements не писать |
| Секрет в описании | Не копировать |
| Повтор того же id | Merge в тот же slug |

Browser MCP не используется. В продукт не пишем.

## 11. Проверка

Фикстура `fixtures/demo-requirement/`: incoming-черновик и ожидаемые `requirements/task-1.md` + фрагмент индекса. Сверка формы, не дословного текста.

`tools/memory_schema.py` проверяет `requirements/*.md`, если папка есть. Отсутствие папки — не ошибка.

**Сценарий 1 — задача с Figma**  
Цель: макет отражён в карточке.  
Шаги: проанализировать задачу со ссылкой на Figma.  
Ожидание: `task-<id>.md`, `source_design: figma`, URL, пункты действие→ожидание; Upservice не изменён.

**Сценарий 2 — без макета**  
Цель: не выдумывать UI.  
Шаги: задача только с текстом.  
Ожидание: карточка, `source_design: none`, gap про дизайн, пункты из текста.

**Сценарий 3 — повтор**  
Цель: один slug.  
Шаги: тот же id ещё раз.  
Ожидание: тот же файл, merge, не второй slug.

Прогон: `py -3 tools/memory_schema.py memory/upservice` → `OK`.

## 12. Реализация (после утверждения spec)

- `.cursor/agents/analyst.md`
- `.cursor/skills/analyze-requirement/SKILL.md`
- Дополнить Librarian и координатора (requirements, не писать в Upservice)
- Расширить `tools/memory_schema.py` + тесты
- `fixtures/demo-requirement/`
- Строка в `AGENTS.md` / `README.md`

Отдельный сервис и запись в Upservice не нужны.
