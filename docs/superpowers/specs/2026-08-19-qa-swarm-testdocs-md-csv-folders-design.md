# QA Swarm — раздельные папки testdocs md и csv

Дата: 2026-08-19  
Статус: черновик на ревью  
Область: раскладка канона testdocs. Опирается на `docs/superpowers/specs/2026-08-14-qa-swarm-test-documentation-design.md`, `docs/superpowers/specs/2026-08-17-qa-swarm-testmo-csv-export-design.md` и `docs/superpowers/specs/2026-08-14-qa-swarm-mcp-verification-design.md`. Не меняет контракт кейса, колонки CSV, merge id и запрет писать в Upservice/Testmo.

Этот spec **заменяет пути** из тех трёх документов: сюит больше не лежит в `testdocs/<slug>.md`, CSV больше не соседний `testdocs/<slug>.csv`. Остальной контракт (поля, id, колонки, роли) без изменений.

## 1. Зачем

В `testdocs/` markdown-сюиты и CSV для Testmo лежат рядом. При нескольких задачах список файлов смешивает канон и выгрузку. Нужно разнести их по папкам, не делая CSV карточкой и не ломая пару slug ↔ active-строки.

## 2. Цели v1

- Канон сюита: `memory/<product-id>/testdocs/md/<slug>.md`.
- CSV выгрузки: `memory/<product-id>/testdocs/csv/<slug>.csv`.
- Индекс: `memory/<product-id>/testdocs/index.md` (не карточка, не в `md/`).
- Жёсткий переход: старые `testdocs/<slug>.md` и `testdocs/<slug>.csv` — ошибка схемы.
- Существующие сюиты Upservice переносятся в том же изменении, что и схема. Смешанной раскладки нет.
- `py -3 tools/memory_schema.py memory/upservice` возвращает `OK`.

Критерий готовности: сценарии раздела 11 проходят; схема по памяти продукта `OK`.

## 3. Вне скоупа v1

- Смена колонок CSV, состава строк, кодировки.
- Запись в Testmo / Upservice.
- Отдельный файл на каждый кейс.
- Пути testdocs в `products/<id>/config.yaml`.
- Совместимость чтения старых соседних `.md`/`.csv`.
- Перенос `index.md` в `md/` или отдельный индекс CSV.
- Рекурсивные подпапки внутри `md/` и `csv/`.

## 4. Зафиксированные решения

| Тема | Решение |
|------|---------|
| Канон | `testdocs/md/<slug>.md`; CSV не карточка |
| CSV | `testdocs/csv/<slug>.csv` |
| Индекс | `testdocs/index.md`; колонка Card: `[<slug>.md](md/<slug>.md)` |
| Пара | тот же `<slug>`, что у требования |
| Переход | только новые пути; legacy в корне `testdocs/` — ошибка |
| Миграция | все уже лежащие сюиты сразу |
| Кто пишет | Librarian через `testdoc_merge.py` и `testdoc_csv.py` |
| CLI хелперов | `--suite` / `--output` без смены флагов; меняются значения путей |
| Пустая `testdocs/` | по-прежнему допустима (нет каталога — не ошибка) |
| Пустые `md/` и `csv/` | могут отсутствовать, пока нет сюитов |

## 5. Архитектура

```text
человек → координатор (generate-testdocs)
       → Scribe → _incoming/testdocs.md
       → Librarian → testdoc_merge.py → testdocs/md/<slug>.md
                  → testdocs/index.md
                  → testdoc_csv.py   → testdocs/csv/<slug>.csv
       → человек (путь сюита, путь CSV, active/orphan, gap)

verify-testdocs читает testdocs/md/<slug>.md
runs/<slug>.md ссылается на тот же slug; схема ищет testdocs/md/<slug>.md
```

Границы без изменений: Scribe не знает про CSV и не читает `testdocs/`. Librarian не составляет CSV вручную. Координатор не пишет `memory/`. Хелпер CSV читает уже записанный `.md`.

Замок `_incoming/` без изменений. Если запись CSV не удалась, incoming не удалять.

## 6. Пути

```text
memory/<product-id>/testdocs/index.md
memory/<product-id>/testdocs/md/<slug>.md
memory/<product-id>/testdocs/csv/<slug>.csv
```

Хелперы путей живут в `tools/memory_schema.py` (чтобы схема, тесты и документация skill не дублировали строки):

- `testdoc_suite_path(root, slug)` → `root/testdocs/md/<slug>.md`
- `testdoc_csv_path(root, slug)` → `root/testdocs/csv/<slug>.csv`

`validate_testdoc_csv(suite_path)` вычисляет CSV так: сюит обязан лежать в каталоге `testdocs/md/`; CSV = `suite_path.parent.parent / "csv" / f"{suite_path.stem}.csv"`. Вызов на файле вне `md/` в дереве памяти не делается. Юнит-тесты хелпера собирают то же дерево (`tmp_path/testdocs/md/` + `tmp_path/testdocs/csv/`), без fallback на соседний `.csv`.

`testdocs/index.md` CSV не перечисляет. `*.csv` карточкой не считается.

Повтор той же задачи: merge в тот же `testdocs/md/<slug>.md`, CSV в `testdocs/csv/<slug>.csv` перезаписывается целиком.

## 7. Контракт схемы

Если каталога `testdocs/` нет — как сейчас, не ошибка.

Если каталог есть:

1. Валидировать сюиты только из `testdocs/md/*.md` (не рекурсивно). Имя `index.md` внутри `md/` пропускать как сюит (не ожидаем такой файл; если появится — не считать карточкой сюита).
2. Для каждого сюита из п.1 — `validate_testdoc_suite` и `validate_testdoc_csv` (CSV в `testdocs/csv/<stem>.csv`). Содержимое CSV — тот же контракт, что в spec выгрузки: заголовок `Name,Folder,Steps,Expected,Id`, только `active`, порядок чек-листа.
3. Каждый `testdocs/csv/*.csv` (не рекурсивно) должен иметь парный сюит в `md/` с тем же stem. `csv/index.csv` — ошибка (нет сюита).
4. В корне `testdocs/` разрешён только `index.md` среди `*.md` и `*.csv`. Любой `testdocs/<slug>.md` (кроме `index.md`) или `testdocs/<slug>.csv` — ошибка вида `legacy testdoc path` (чтобы старая раскладка не прошла схему).
5. Прогон `runs/`: карточка ищет testdoc по `testdocs/md/<testdoc>.md`, не по `testdocs/<testdoc>.md`. Текст ошибки — `missing testdoc testdocs/md/<slug>.md`.

Сверка CSV по разобранным полям — без изменений.

## 8. Роли и skill

### Координатор

В отчёте `generate-testdocs` указывает `testdocs/md/<slug>.md` и `testdocs/csv/<slug>.csv`. `verify-testdocs` ищет сюит в `testdocs/md/`. Строка в `.cursor/rules/coordinator.mdc`: verify только если `testdocs/md/<slug>.md` имеет `active`.

### Scribe

Без изменений.

### Librarian

```text
py -3 tools/testdoc_merge.py --incoming memory/<product-id>/raw/_incoming/testdocs.md --existing memory/<product-id>/testdocs/md/<slug>.md --output memory/<product-id>/testdocs/md/<slug>.md
```

Индекс: ссылка Card `md/<slug>.md`.

```text
py -3 tools/testdoc_csv.py --suite memory/<product-id>/testdocs/md/<slug>.md --output memory/<product-id>/testdocs/csv/<slug>.csv
```

При goal `run`: открывать `testdocs/md/<slug>.md`.

### Skill `generate-testdocs` / `verify-testdocs`

Пути сюита и CSV — `md/` и `csv/`. Verifier получает `memory/<product-id>/testdocs/md/<slug>.md`.

Правило `memory-card.mdc` и README: канон в `testdocs/md/`, выгрузка в `testdocs/csv/`.

## 9. Поток

1. Как в spec тест-доков: замок, `ready` требование, Scribe, merge — output в `testdocs/md/<slug>.md`.
2. Librarian обновляет `testdocs/index.md` со ссылкой `md/<slug>.md`.
3. Librarian вызывает `testdoc_csv.py` с output `testdocs/csv/<slug>.csv`.
4. Схема. Не `OK` — incoming на месте.
5. Координатор: сюит, CSV, счётчики, gap.

Добор CSV без Scribe: тот же CLI, `--suite` на `md/<slug>.md`, `--output` на `csv/<slug>.csv`.

Миграция уже лежащих файлов: `testdocs/<slug>.md` → `testdocs/md/<slug>.md`, `testdocs/<slug>.csv` → `testdocs/csv/<slug>.csv`, поправить ссылки в `testdocs/index.md`. Делает реализация spec, не runtime-координатор и не generate-testdocs.

## 10. Ошибки

| Ситуация | Поведение |
|----------|-----------|
| Нет `testdocs/md/<slug>.md` при generate/verify | Как сейчас: стоп / missing testdoc, путь в сообщении новый |
| Нет парного `testdocs/csv/<slug>.csv` | Ошибка схемы `missing testdoc CSV` |
| `testdocs/csv/<slug>.csv` без `md/<slug>.md` | Ошибка схемы `csv without testdoc suite` |
| `testdocs/<slug>.md` или `testdocs/<slug>.csv` в корне testdocs | Ошибка схемы `legacy testdoc path` |
| Рассинхрон CSV с active | Как в spec выгрузки |
| `testdocs/index.md` | Не сюит, CSV не требует |
| Секрет в `.md` | Как сейчас на сюите |

## 11. Проверка

Фикстура `fixtures/demo-testdoc/expected/testdocs/`: `md/task-1.md`, `csv/task-1.csv`, `index.md` со ссылкой `(md/task-1.md)`. `existing/testdocs/task-1.md` переносится в `existing/testdocs/md/task-1.md` (CSV для existing не нужен: merge читает только `.md`).

`fixtures/demo-run/testdocs/task-1.md` — изолированный файл для юнитов run/merge; дерево памяти продукта и `validate_memory_tree` используют `testdocs/md/`. Тест `test_memory_tree_run_requires_existing_testdoc` ожидает `missing testdoc testdocs/md/task-1.md`.

Юнит-тесты `validate_testdoc_csv` и «сюит без CSV» кладут файлы в `tmp_path/testdocs/md/` и `tmp_path/testdocs/csv/`. Тест stray CSV: `testdocs/csv/index.csv` и/или legacy `testdocs/index.csv` в корне.

**Сценарий 1 — generate-testdocs**  
Цель: сюит и CSV в разных папках.  
Ожидание: `testdocs/md/<slug>.md` и `testdocs/csv/<slug>.csv`; схема `OK`; в корне `testdocs/` нет `<slug>.md`/`.csv`.

**Сценарий 2 — схема отвергает legacy**  
Цель: жёсткий переход.  
Шаги: дерево с `testdocs/task-1.md` (или `.csv`) в корне.  
Ожидание: ошибка `legacy testdoc path`.

**Сценарий 3 — миграция памяти**  
Цель: текущие сюиты Upservice валидны.  
Ожидание: все бывшие пары перенесены; `index.md` ссылается на `md/`; `py -3 tools/memory_schema.py memory/upservice` → `OK`.

Прогон: `py -3 -m pytest tests/test_testdoc_csv.py tests/test_memory_schema.py tests/test_testdoc_merge.py -v` и `py -3 tools/memory_schema.py memory/upservice` → `OK`.

## 12. Реализация (после утверждения spec)

- Хелперы путей + `validate_testdoc_csv` / обход `testdocs/` / lookup run→testdoc в `tools/memory_schema.py`
- Тесты и фикстуры `demo-testdoc` (expected `md/` + `csv/`, existing `md/`)
- Librarian, `generate-testdocs`, `verify-testdocs`, verifier, coordinator.mdc, memory-card.mdc, README
- Правка путей в трёх родительских spec (разделы путей), без смены их контракта полей
- Перенос файлов в `memory/upservice/testdocs/`

Клиент Testmo не нужен.

## 13. Что сознательно отложено

- Настраиваемые имена папок `md`/`csv`.
- Индекс CSV.
- Совместимый fallback на соседний файл.
