# QA Swarm — CSV выгрузка тест-кейсов для Testmo

Дата: 2026-08-17  
Статус: черновик на ревью  
Область: продолжение подпроекта 3 (тест-документация). Опирается на `docs/superpowers/specs/2026-08-14-qa-swarm-test-documentation-design.md`. Не заменяет канон сюита и не открывает запись в TMS.

## 1. Зачем

Канонические кейсы лежат в `testdocs/md/<slug>.md`. Чтобы импортировать их в Testmo, нужен CSV, который мастер импорта сопоставляет с полями шаблона. Файл должен появляться вместе с генерацией сюита, с теми же стабильными `tc-…` id.

Канон по-прежнему markdown в git. CSV — производный артефакт для ручного импорта. Агенты не вызывают Testmo API и не пишут в Upservice.

## 2. Цели v1

- После успешного merge сюита появляется `testdocs/csv/<slug>.csv`.
- Одна строка CSV = один кейс `active`. Колонки фиксированы и мапятся на шаблон Testmo «case text» (или аналог) через мастер.
- Тот же Python-хелпер можно запустить отдельно, чтобы дописать CSV к уже лежащим сюитам.
- `tools/memory_schema.py` считает память невалидной, если CSV отсутствует или расходится с `active` кейсами.
- Координатор в отчёте `generate-testdocs` указывает путь CSV. «Тест-доки готовы» по-прежнему только если схема `OK`.

Критерий готовности: сценарии в разделе 11 проходят; `py -3 tools/memory_schema.py memory/upservice` возвращает `OK`.

## 3. Вне скоупа v1

- Запись в Testmo API / CLI Testmo (импорт делает человек).
- Обновление уже импортированных кейсов при повторной выгрузке (мастер Testmo в этом контуре не вызывается).
- Иерархия папок вида `Upservice > task-<id>` (колонка `Folder` = заголовок сюита; иерархию можно добавить позже, не меняя набор колонок).
- Несколько строк на один кейс (отдельные шаги). В v1 у кейса один `action` и один `expected`.
- CSV от Scribe (у Scribe нет финальных id).
- Запись в Upservice.
- Автозапуск `generate-testdocs` из других skill.
- Выгрузка `orphan` кейсов.

## 4. Зафиксированные решения

| Тема | Решение |
|------|---------|
| Канон | `testdocs/md/<slug>.md`; CSV не карточка |
| Где файл | `memory/<product-id>/testdocs/csv/<slug>.csv`, в git |
| Когда писать | Librarian сразу после успешного `testdoc_merge.py` |
| Кто рендерит | Python-хелпер `tools/testdoc_csv.py`, не агент |
| Какие кейсы | Только `status: active`, порядок = чек-лист |
| Колонки | `Name,Folder,Steps,Expected,Id` |
| `Name` | `title` кейса |
| `Folder` | `title` сюита (frontmatter) |
| `Steps` | `action` |
| `Expected` | `expected` |
| `Id` | id кейса (`tc-<prefix>-<n>`) |
| Кодировка | UTF-8 без BOM, разделитель запятая, `\n` |
| Пустой сюит | CSV только с заголовком |
| Testmo / Upservice | Не вызываем, не пишем |

Текст полей копируется из markdown без перефраза. Пустой `title` кейса даёт пустой `Name`; хелпер заголовок не выдумывает (Testmo Name обязателен при импорте — это дефект сюита, не CSV). Кавычки, запятые и переносы экранирует стандартный `csv.writer` (`QUOTE_MINIMAL`).

## 5. Архитектура

```text
человек → координатор (generate-testdocs)
       → Scribe → _incoming/testdocs.md
       → Librarian → testdoc_merge.py → testdocs/md/<slug>.md
                  → testdoc_csv.py   → testdocs/csv/<slug>.csv
                  → memory_schema.py
       → человек (путь сюита, путь CSV, active/orphan, gap)
человек импортирует CSV в Testmo вручную
```

Границы:

- Scribe не знает про CSV и не назначает id.
- Librarian не составляет строки CSV сам: только вызывает хелпер. Не ходит в Testmo.
- Координатор не пишет `memory/`.
- Хелпер читает уже записанный `.md` (после merge), не incoming без id.

Замок `_incoming/` без изменений. Если запись CSV не удалась, Librarian **не** удаляет incoming и не считает канон готовым.

Отдельный прогон хелпера по существующему сюиту допустим (добор CSV без нового Scribe).

## 6. Пути

```text
memory/<product-id>/testdocs/md/<slug>.md
memory/<product-id>/testdocs/csv/<slug>.csv
```

`<slug>` тот же, что у сюита и карточки требований. `testdocs/index.md` CSV не перечисляет. Файл `*.csv` карточкой не считается: нет YAML-frontmatter, `validate_testdoc_suite` его не парсит как markdown. Сюит или CSV в корне `testdocs/` (кроме `index.md`) — `legacy testdoc path` (см. `docs/superpowers/specs/2026-08-19-qa-swarm-testdocs-md-csv-folders-design.md`).

Повтор той же задачи: merge в тот же `.md`, CSV перезаписывается целиком из актуальных `active` кейсов (не merge по строкам CSV).

## 7. Контракт CSV

Первая строка — заголовок, байт в байт имена колонок:

```text
Name,Folder,Steps,Expected,Id
```

Дальше ноль или больше строк данных. Для сюита из фикстуры `fixtures/demo-testdoc/expected/testdocs/md/task-1.md` (три `active`, один `orphan` `tc-1-2`) в CSV ровно три строки данных: `tc-1-1`, `tc-1-3`, `tc-1-4` в порядке чек-листа. `tc-1-2` отсутствует.

CLI:

```text
py -3 tools/testdoc_csv.py --suite <path.md> --output <path.csv>
```

`--suite` обязателен и должен существовать. `--output` обязателен. Хелпер создаёт родительский каталог output при необходимости. Код 0 — файл записан; stdout — путь output. Код 1 — сюит отсутствует, не читается или не парсится как testdoc; output не пишется (частичный файл не оставлять: писать во временный и заменять, либо не создавать).

Маппинг в мастере Testmo (подсказка человеку, не автоматизация): Name → Name, Folder → Folder, Steps → шаги, Expected → ожидаемый результат, Id → automation/external id или custom-поле, если в шаблоне ещё нет. Режим строк: каждая строка — один кейс.

## 8. Роли и skill

### Координатор

После Librarian дополнительно сообщает путь CSV. Не импортирует в Testmo. Не запускает отдельный контур TMS.

### Scribe

Без изменений.

### Librarian

После успешного `testdoc_merge.py` и обновления `testdocs/index.md` вызывает:

```text
py -3 tools/testdoc_csv.py --suite memory/<product-id>/testdocs/md/<slug>.md --output memory/<product-id>/testdocs/csv/<slug>.csv
```

Затем `py -3 tools/memory_schema.py memory/<product-id>`. Только после `OK` удаляет incoming. Не вызывает Testmo.

### Skill `generate-testdocs`

Шаг Librarian расширяется: пишет `.md` и `.csv`. В отчёте — оба пути. Запрет писать в Testmo сохраняется (CSV в git ≠ запись в TMS).

## 9. Поток

1. Как в spec тест-доков: замок, `ready` требование, Scribe, merge.
2. Librarian вызывает `testdoc_csv.py` на только что записанный сюит.
3. Схема. Не `OK` — incoming на месте, координатор не говорит «готово».
4. Координатор: сюит, CSV, счётчики, gap.

Добор без Scribe: человек или реализация первого прогона гоняет хелпер по уже лежащим `testdocs/md/*.md` (в т.ч. `task-5210629`), чтобы схема не падала на старых сюитах без CSV.

## 10. Ошибки

| Ситуация | Поведение |
|----------|-----------|
| Нет `.md` сюита | CLI код 1, CSV не писать |
| Сюит не парсится | CLI код 1, CSV не писать |
| Запись CSV не удалась после merge | Incoming не удалять, канон не считать готовым |
| Нет парного CSV при наличии сюита `testdocs/md/*.md` (`index.md` не сюит) | Ошибка схемы |
| `testdocs/csv/*.csv` без парного сюита, в том числе `csv/index.csv` | Ошибка схемы |
| Заголовок не `Name,Folder,Steps,Expected,Id` | Ошибка схемы |
| Число строк ≠ число `active` | Ошибка схемы |
| Порядок или поля не совпадают с чек-листом / кейсами | Ошибка схемы |
| В CSV есть `orphan` id | Ошибка схемы (как рассинхрон id) |
| Секрет в `.md` | Как сейчас на сюите; CSV из такого файла не канонизировать |

Сверка схемы идёт по **разобранным полям** (`csv.reader`), не по сырым байтам: различие `\r\n` / quoting не должно давать ложный OK, если значения полей другие, и не должно падать, если хелпер экранирует допустимым `QUOTE_MINIMAL`. Заголовок сравнивается как список имён колонок.

`testdocs/index.md` и отсутствие каталога `testdocs/` — без изменений ядра.

## 11. Проверка

Фикстура: `fixtures/demo-testdoc/expected/testdocs/md/task-1.md` и `fixtures/demo-testdoc/expected/testdocs/csv/task-1.csv`. Юнит-тесты хелпера: три `active` без orphan; пустой/`draft` сюит → только заголовок; поле с запятой и кавычкой экранируется и обратно читается. Схема: нет CSV; лишний CSV; рассинхрон `Id`.

**Сценарий 1 — generate-testdocs**  
Цель: CSV появляется вместе с сюитом.  
Шаги: команда на задачу с `ready` требованиями.  
Ожидание: `testdocs/md/<slug>.md` и `testdocs/csv/<slug>.csv`; строки = `active`; Testmo не вызван; схема `OK`.

**Сценарий 2 — повтор**  
Цель: CSV следует за merge id.  
Шаги: тот же slug ещё раз; один пункт тот же, один новый, один изменённый.  
Ожидание: CSV перезаписан; старый id на месте; новый id в новой строке; `orphan` в CSV нет.

**Сценарий 3 — добор**  
Цель: старый сюит без CSV становится валидным.  
Шаги: `testdoc_csv.py` на существующий `.md`.  
Ожидание: CSV в `testdocs/csv/`; схема `OK`.

Прогон: `py -3 -m pytest tests/test_testdoc_csv.py tests/test_memory_schema.py tests/test_testdoc_merge.py -v` и `py -3 tools/memory_schema.py memory/upservice` → `OK`.

## 12. Реализация (после утверждения spec)

- `tools/testdoc_csv.py` + `tests/test_testdoc_csv.py`
- Расширить `tools/memory_schema.py` (соседний CSV, лишние CSV)
- `fixtures/demo-testdoc/expected/testdocs/csv/task-1.csv`
- Librarian / `generate-testdocs` skill / при необходимости координатор (путь CSV в отчёте)
- Добор CSV для уже лежащих сюитов в `memory/upservice/testdocs/`
- Строка в README, если там перечислены артефакты testdocs

Клиент Testmo не нужен.

## 13. Что сознательно отложено

- Иерархия `Folder` (`product > slug`).
- Режим нескольких шагов на кейс.
- Синхронизация повторного импорта (матч по `Id` внутри Testmo).
- Пометка CSV `stale` отдельно от сюита: CSV всегда пересобирается из текущего `.md`.
