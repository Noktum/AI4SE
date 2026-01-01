# Практическое задание 1. Индекс репозитория для SE агента

| | |
|---|---|
| Баллы | **2.0 из 10** за курс |
| Выдача | `<дата>`, после лекции 3 "Program structure" |
| Срок | `<дата>` 23:59 МСК, две недели после выдачи |
| Сдача | ссылка на приватный GitHub-репозиторий |
| Защита | 7-10 минут на ближайшем семинаре после срока |

## Идея

SE агент не знает структуру конкретного репозитория заранее. Чтобы он мог спрашивать
"где определен символ?", "кто вызывает функцию?" или "есть ли путь вызовов между функциями?",
нужно сначала построить представление репозитория.

В этой работе вы построите небольшой **repository index** для Python:

```text
Python source -> Tree-sitter CST -> symbols + imports + call sites ->
-> name resolution -> approximate call graph -> definition / references / callers / callees / path
```

Цель -- не полный анализ Python, а инструмент с понятными границами применимости.
Все понятия из этого задания разобраны в лекции 3 (части II и III).

---

## Среда и версии

Для задания нужен только **uv**: <https://docs.astral.sh/uv/getting-started/installation/>.

Starter repository фиксирует версии:

| пакет | версия |
|---|---|
| Python | 3.12 |
| tree-sitter | 0.25.2 |
| tree-sitter-python | 0.25.0 |
| networkx | ≥ 3.4 |
| ruff | 0.16.9 |
| pytest | ≥ 8 |

> **Не обновляйте tree-sitter до 0.26.0.** В этой версии `Node.start_point.row` портит память на
> строках после 256, и индексатор падает с `Segmentation fault` на любом крупном файле FastAPI.
> Исправление есть в upstream, но пока не попало в релиз.

После клонирования starter repository достаточно сделать:

```bash
uv sync
```

`uv` сам создаст виртуальное окружение и при необходимости установит нужную версию Python.

Основные команды:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run repo-map --help
```

---

## Репозиторий для анализа

Основная проверка выполняется на FastAPI:

- <https://github.com/fastapi/fastapi>
- release `0.141.1`, commit `95f8322`
- analysis root: каталог пакета `fastapi/` внутри клона

Клонируйте FastAPI **рядом** с вашим решением. Все команды ниже предполагают такую раскладку:

```text
work/
├── repo-map/     ваше решение (из starter repository)
└── fastapi/      клон FastAPI
    └── fastapi/  ← это --root
```

```bash
cd work
git clone https://github.com/fastapi/fastapi.git
git -C fastapi checkout 95f8322
```

FastAPI не нужно импортировать или исполнять: анализ выполняется только по исходному коду.

---

## Starter repository

Starter выдается одним файлом `repo-map-starter.bundle` в `<LMS / канал курса>`. Это git-репозиторий
целиком (git bundle): из него клонируют так же, как с сервера.

```bash
cd work
git clone repo-map-starter.bundle repo-map
cd repo-map
git remote remove origin    # origin указывает на файл bundle, он больше не нужен
```

Внутри одна ветка `main` с одним коммитом:

```text
src/repo_map/
    parser.py      настройка Tree-sitter, node_text(), line_of()
    model.py       Symbol, Import, CallSite, Reference
    index.py       именование модулей (готово) и каркас RepoIndex
    graph.py       каркас call graph
    cli.py         CLI и формат JSON (готово)

scripts/
    print_tree.py  печать syntax tree файла

tests/
    fixtures/tiny_pkg/       маленький пакет для первых шагов и экспериментов
    test_parser_smoke.py     проверка окружения
    test_fastapi_smoke.py    публичные smoke tests на FastAPI

pyproject.toml, uv.lock, .python-version
ASSIGNMENT.md                это условие
README.md, REPORT.md         шаблоны для сдачи
```

Starter снимает с вас все, что не относится к анализу: окружение, packaging, разбор аргументов и
печать JSON. `cli.py` уже вызывает методы `RepoIndex` и печатает результат в формате из раздела
[Запросы и формат вывода](#запросы-и-формат-вывода). Вам остается реализовать `RepoIndex` и
`CallGraph`. Структуру внутри можно менять как угодно, если CLI выдает тот же формат.

---

## Как начать

### 1. Запустите starter

```bash
uv sync
uv run pytest -q
uv run repo-map --help
```

Тесты должны пройти, а любой запрос пока отвечает `repo-map: not implemented yet: RepoIndex.build`.

### 2. Посмотрите syntax tree

```bash
uv run python scripts/print_tree.py tests/fixtures/tiny_pkg/a.py
```

```text
module [1:0]
  import_statement [1:0]
    name: dotted_name [1:7]
      identifier [1:7]  'json'
  ...
  import_from_statement [4:0]
    module_name: relative_import [4:5]
      import_prefix [4:5]  '.'
      dotted_name [4:6]
        identifier [4:6]  'b'
    name: aliased_import [4:15]
      name: dotted_name [4:15]
        identifier [4:15]  'helper'
      alias: identifier [4:25]  'run_helper'
  function_definition [7:0]
    name: identifier [7:4]  'public_api'
    parameters: parameters [7:14]
      identifier [7:15]  'value'
    body: block [8:4]
      return_statement [8:4]
        call [8:11]
          function: identifier [8:11]  'run_helper'
          arguments: argument_list [8:21]
            identifier [8:22]  'value'
```

`name:`, `body:`, `function:` -- это поля (fields) узла. Для начала достаточно нескольких свойств
`Node`:

```text
node.type
node.named_children
node.child_by_field_name("name")
node.start_point        строки с 0; в выводе нужны строки с 1, см. line_of()
node.text
```

Две особенности грамматики, о которые легко споткнуться:

- `async def` -- это тот же `function_definition` с дочерним узлом `async`;
- декораторы лежат в `decorated_definition` рядом с определением, а не внутри него.

### 3. Постройте definitions index

Сначала работайте только с `tests/fixtures/tiny_pkg/`. Извлеките модули, классы, функции
(включая `async`) и методы. Удобная первая структура: `qualified_name -> Symbol`.

```text
tiny_pkg
tiny_pkg.a.public_api
tiny_pkg.b.helper
tiny_pkg.b.Formatter
tiny_pkg.b.Formatter._wrap
```

### 4. Добавьте imports

Поддержите все шесть форм:

```python
import module
import module as alias
from module import symbol
from module import symbol as alias
from .module import symbol
from ..module import symbol
```

Сначала сохраните imports как есть, затем разрешайте alias в qualified name.

### 5. Добавьте call sites

Для каждого вызова храните выражение, файл и строку, scope (кто вызывает) и результат
разрешения. В fixture вызов

```python
return run_helper(value)
```

должен превратиться в ребро

```text
tiny_pkg.a.public_api -> tiny_pkg.b.helper
```

### 6. Постройте граф и запросы

Каждый вызов, разрешенный в символ проекта, дает ребро `caller -> callee`. NetworkX уже в
зависимостях. Когда fixture работает целиком, переходите к FastAPI.

---

## Модель: символы и имена

### Qualified names

`--root` указывает на каталог пакета, его имя становится пакетом верхнего уровня. Это уже
реализовано в `index.py`:

```text
fastapi/__init__.py           fastapi
fastapi/applications.py       fastapi.applications
fastapi/openapi/utils.py      fastapi.openapi.utils
```

Имя символа -- имя модуля плюс цепочка вложенных определений:

```text
fastapi.applications.FastAPI                  class
fastapi.applications.FastAPI.openapi          method
fastapi.applications.FastAPI.setup.openapi    function, вложенная в метод setup
fastapi.openapi.utils.get_openapi             function
```

| kind | что это |
|---|---|
| `module` | файл `.py`; `line` = 1 |
| `class` | `class` на любом уровне |
| `method` | `def` или `async def` прямо в теле класса |
| `function` | любой другой `def` или `async def`, включая вложенные |

Лямбды символов не создают. Скрытые каталоги (`.agents/` и т.п.) и
`__pycache__/` пропускаются.

### Scope

Каждый call site и каждая reference относятся к ближайшему охватывающему символу:

1. функция или метод;
2. если их нет -- класс (код в теле класса);
3. если нет и класса -- модуль.

Декоратор вычисляется в охватывающей области, поэтому вызовы в декораторе относятся к ней, а не к
декорированной функции.

### Файл и строка

`file` -- путь относительно родителя `--root`, через `/`: `fastapi/applications.py`.
`line` -- номер строки **с 1**. Для определения это строка с `def` или `class` (у функции с
декоратором -- не строка декоратора), для вызова -- строка, где начинается выражение вызова.

---

## Разрешение имен

У каждого call site один из трех статусов:

| статус | значение | пример |
|---|---|---|
| `internal` | цель -- символ анализируемого пакета | `run_helper(x)` -> `tiny_pkg.b.helper` |
| `external` | цель -- имя вне пакета | `json.dumps(x)` -> `json.dumps` |
| `unresolved` | цель нельзя установить по поддержанным правилам | `formatter.format(x)` |

Встроенные функции (`len`, `isinstance`) можно относить к `external` (как `builtins.len`) или к
`unresolved`, но не к `internal`.

### Обязательные правила

| правило | пример | результат |
|---|---|---|
| имя из того же модуля | `normalize(value)` в `b.py` | `tiny_pkg.b.normalize` |
| вложенная функция | `def outer(): def inner(): …; inner()` | `….outer.inner` |
| `from`-import, alias, relative | `from .b import helper as run_helper`; `run_helper()` | `tiny_pkg.b.helper` |
| import модуля и атрибут | `from . import b`; `b.helper()` | `tiny_pkg.b.helper` |
| то же через `import` | `import pkg.b as b`; `b.helper()`; `import pkg.b`; `pkg.b.helper()` | `pkg.b.helper` |
| re-export, в том числе цепочкой | `from tiny_pkg import public_api` | `tiny_pkg.a.public_api` |
| вызов класса | `b.Formatter()` | `tiny_pkg.b.Formatter` (сам класс, не `__init__`) |
| `self.method()` | `self._wrap(x)` в методе `Formatter` | `tiny_pkg.b.Formatter._wrap` |
| перекрытие локальным именем | `def f(helper): helper()` | **не** `tiny_pkg.b.helper` |

Пояснения:

- `self` -- первый параметр метода. `self.m()` разрешается, только если `m` определен в теле того же
  класса.
- Re-export -- это обычный import: имя, импортированное в модуль, видно как атрибут этого модуля.
  Чаще всего так устроен `__init__.py`:

  ```python
  # fastapi/__init__.py
  from .applications import FastAPI as FastAPI
  ```

  поэтому `fastapi.FastAPI` ведет к определению в `fastapi/applications.py`.
- Перекрытие: если имя -- параметр функции или цель простого присваивания `name = …` в ней, вызов
  этого имени не должен разрешаться в одноименную функцию модуля.

### Что можно оставить unresolved

Не требуются:

- type inference и произвольный `obj.method()`;
- методы базовых классов и dispatch по наследованию, `super()`, `cls.method()`;
- `self` внутри функции, вложенной в метод;
- imports внутри функций;
- `getattr`, monkey patching, dynamic imports, `import *`;
- семантика декораторов во время выполнения;
- dependency injection FastAPI;
- data-flow и taint analysis.

Если цель неизвестна, не угадывайте ее. Например, в `fastapi/routing.py`

```python
return await dependant.call(**values)
```

дает

```json
{"expression": "dependant.call", "file": "fastapi/routing.py", "line": 352, "reason": "dynamic receiver"}
```

**Ложное уверенное ребро хуже честного `unresolved`.** Если вы все же разрешаете что-то из списка
выше, правило должно быть корректным: скрытые проверки эти случаи не требуют, но ложное ребро
засчитывается как ошибка.

---

## Запросы и формат вывода

### Команды

```bash
uv run repo-map definition SYMBOL --root ROOT
uv run repo-map references SYMBOL --root ROOT
uv run repo-map callers    SYMBOL --root ROOT
uv run repo-map callees    SYMBOL --root ROOT
uv run repo-map path SOURCE TARGET --root ROOT
```

- **definition** -- фактическое определение с учетом imports и re-export.
- **references** -- разрешенные ссылки на символ. Обязательны виды `import` и `call`; другие
  использования (базовый класс, аргумент, декоратор) можно добавить как `other`.
- **callers** -- символы, содержащие разрешенный вызов этого символа. Обычно это функции и методы,
  но может быть класс или модуль, если вызов стоит в их теле.
- **callees** -- вызовы внутри функции или метода: разрешенные цели внутри проекта, внешние вызовы и
  unresolved.
- **path** -- кратчайший ориентированный путь в вашем приближенном call graph.

`SYMBOL` -- любое из двух:

- qualified name символа из индекса, включая вложенные: `fastapi.applications.FastAPI.setup.openapi`;
- имя, которое через imports и re-export ведет к символу: `fastapi.FastAPI`, `tiny_pkg.public_api`.

В выводе всегда используется canonical qualified name, то есть имя по месту определения.

### Формат JSON

Вывод -- один JSON-объект в stdout. Ниже ответы для `--root tests/fixtures/tiny_pkg`. Поля сверх
перечисленных добавлять можно, проверка их игнорирует.

**definition** -- `results` это список, потому что одно имя бывает определено дважды (в двух ветках
`if` или `try`):

```json
{
  "query": "definition",
  "input": "tiny_pkg.public_api",
  "symbol": "tiny_pkg.a.public_api",
  "results": [
    {"qualified_name": "tiny_pkg.a.public_api", "kind": "function",
     "file": "tiny_pkg/a.py", "line": 7, "async": false}
  ]
}
```

**references** для `tiny_pkg.b.helper`:

```json
{
  "query": "references",
  "input": "tiny_pkg.b.helper",
  "symbol": "tiny_pkg.b.helper",
  "results": [
    {"kind": "import", "file": "tiny_pkg/a.py", "line": 4, "scope": "tiny_pkg.a"},
    {"kind": "call", "file": "tiny_pkg/a.py", "line": 8, "scope": "tiny_pkg.a.public_api"},
    {"kind": "call", "file": "tiny_pkg/b.py", "line": 11, "scope": "tiny_pkg.b.Formatter.format"}
  ]
}
```

**callers** для `tiny_pkg.b.helper` -- элементы в том же формате, что в `definition`:

```json
{
  "query": "callers",
  "input": "tiny_pkg.b.helper",
  "symbol": "tiny_pkg.b.helper",
  "results": [
    {"qualified_name": "tiny_pkg.a.public_api", "kind": "function",
     "file": "tiny_pkg/a.py", "line": 7, "async": false},
    {"qualified_name": "tiny_pkg.b.Formatter.format", "kind": "method",
     "file": "tiny_pkg/b.py", "line": 10, "async": false}
  ]
}
```

**callees** для `tiny_pkg.a.render`:

```json
{
  "query": "callees",
  "input": "tiny_pkg.a.render",
  "symbol": "tiny_pkg.a.render",
  "results": [
    {"qualified_name": "tiny_pkg.b.Formatter", "kind": "class",
     "file": "tiny_pkg/b.py", "line": 9, "async": false}
  ],
  "external": [
    {"expression": "json.dumps", "target": "json.dumps", "file": "tiny_pkg/a.py", "line": 13}
  ],
  "unresolved": [
    {"expression": "formatter.format", "file": "tiny_pkg/a.py", "line": 13,
     "reason": "local variable"}
  ]
}
```

`reason` -- короткая причина в свободной форме: `local variable`, `dynamic receiver`,
`not defined in class`, `unknown name`.

**path** от `tiny_pkg.public_api` к `tiny_pkg.b.normalize`:

```json
{
  "query": "path",
  "source": "tiny_pkg.a.public_api",
  "target": "tiny_pkg.b.normalize",
  "path": ["tiny_pkg.a.public_api", "tiny_pkg.b.helper", "tiny_pkg.b.normalize"]
}
```

Если пути нет, `"path": null`. Если кратчайших путей несколько, подходит любой.

### Ошибки

| ситуация | stdout | stderr | код выхода |
|---|---|---|---|
| запрос выполнен, даже с пустым результатом | JSON | -- | 0 |
| символ не найден | пусто | `repo-map: unknown symbol: …` | 1 |
| неверные аргументы, `--root` не каталог | пусто | usage | 2 |

Все это уже реализовано в `cli.py`, если `RepoIndex.resolve` возвращает `None` для неизвестного
имени.

---

## Публичные проверки

Те же проверки лежат в `tests/test_fastapi_smoke.py`:

```bash
uv run pytest -q -m fastapi
```

| запрос | ожидаемый результат |
|---|---|
| `definition fastapi.FastAPI` | `fastapi.applications.FastAPI` в `fastapi/applications.py` |
| `definition fastapi.APIRouter` | `fastapi.routing.APIRouter` в `fastapi/routing.py` |
| `callers fastapi.openapi.utils.get_openapi` | среди результатов `fastapi.applications.FastAPI.openapi` |
| `path fastapi.applications.FastAPI.openapi fastapi.openapi.utils.get_openapi_path` | путь ниже |

```text
fastapi.applications.FastAPI.openapi
-> fastapi.openapi.utils.get_openapi
-> fastapi.openapi.utils.get_openapi_path
```

Полный индекс FastAPI (48 файлов) должен строиться за несколько секунд.

Скрытая проверка добавляет запросы к FastAPI и небольшой synthetic fixture с известным ground
truth, по одному случаю на каждое обязательное правило и на каждый пункт из "можно оставить
unresolved". Она проверяет обе стороны: что обязательные ребра найдены и что ложных ребер нет.

---

## Ограничения на решение

- Синтаксический анализ -- только через Tree-sitter. Модуль `ast`, jedi, pyright, LSP-серверы и
  другие готовые анализаторы Python для основной логики использовать нельзя.
- Зависимости времени выполнения: стандартная библиотека, `tree-sitter`, `tree-sitter-python`,
  `networkx`. Для тестов и разработки можно добавлять что угодно.
- Можно обходить дерево вручную или через Tree-sitter Queries, подходят оба способа.

---

## Что сдать

### Код

Ваш репозиторий, созданный из starter repository, с реализацией и тестами. Тесты на собственный
fixture обязательны: хотя бы по одному на каждое обязательное правило разрешения имен.

Перед сдачей должны проходить:

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

### `README.md`

Шаблон уже в starter. Кратко:

- как запустить проект;
- по одному примеру на каждый из пяти запросов;
- что добавлено к базовому формату JSON, если добавлено;
- как запустить проверки.

### `REPORT.md`

Около одной страницы, шаблон в starter:

1. **Представление** -- что хранится в индексе.
2. **Разрешение имен** -- какие правила поддержаны, с примером на каждое.
3. **Ограничение** -- один реальный unresolved или неточный вызов из FastAPI: файл, строка, почему,
   что понадобилось бы для правильного ответа.
4. **Использование AI** -- что делегировали кодинг агенту или LLM, что пришлось проверить или
   исправить и как вы это заметили.

### Как сдать

1. Создайте на GitHub **пустой** приватный репозиторий: без README, `.gitignore` и лицензии.
2. Подключите его к своему клону и отправьте историю:

   ```bash
   git remote add origin git@github.com:<login>/repo-map.git
   git push -u origin main
   ```

3. При сдаче надо будет добавить  преподавателей в collaborators: `<GitHub-логин>`.
4. Поставьте на сдаваемый коммит тег `lab1` и запушьте его: `git tag lab1 && git push origin lab1`.
5. Отправьте ссылку на репозиторий в `<LMS / форма>` до срока.

Проверяется коммит с тегом `lab1`. Опоздание: −0.2 балла за каждые сутки.

---

## Использование AI

Coding agents и LLM **разрешены и приветствуются**: Codex, Claude Code, Gemini CLI, OpenCode и
другие. Они помогут:

- разобраться с Tree-sitter;
- исследовать FastAPI;
- написать реализацию и тесты;
- найти ошибку;
- сделать code review.

На защите нужно понимать собственное решение: представление индекса, разрешение imports,
происхождение конкретного ребра графа и причины unresolved. Если ключевую часть решения вы не можете
объяснить, баллы за соответствующий раздел не начисляются.

---

## Оценка

| часть | баллы | что проверяется |
|---|---|---|
| Tree-sitter и представление | 0.5 | все виды символов, qualified names, scopes, файлы и строки; индекс строится на всем `fastapi/` |
| Imports и разрешение имен | 0.5 | все обязательные правила; нет ложных ребер на случаях из «можно оставить unresolved» |
| Запросы и call graph | 0.5 | пять запросов, формат JSON, публичные и скрытые проверки |
| Качество | 0.25 | тесты, README, понятные ошибки, `ruff check` и `ruff format --check` |
| Понимание | 0.25 | осмысленное ограничение в `REPORT.md` |

---

## Защита

Ориентир: **5–7 минут**. Нужно:

1. выполнить один запрос на FastAPI;
2. объяснить, откуда взялось одно ребро графа;
3. показать один unresolved-вызов или ограничение;
4. ответить на вопрос по архитектуре решения.

Может быть дан небольшой новый фрагмент Python-кода с вопросом: "как ваш анализатор его
обработает?".

---

## Материалы

1. **uv -- Getting Started**: <https://docs.astral.sh/uv/getting-started/>
2. **py-tree-sitter -- Usage**: <https://github.com/tree-sitter/py-tree-sitter#usage>
3. **Tree-sitter Queries**: <https://tree-sitter.github.io/tree-sitter/using-parsers/queries/>
4. **Query syntax**: <https://tree-sitter.github.io/tree-sitter/using-parsers/queries/1-syntax.html>
5. **Python grammar** (имена узлов и полей -- в `src/node-types.json`):
   <https://github.com/tree-sitter/tree-sitter-python>
6. **NetworkX shortest paths**:
   <https://networkx.org/documentation/stable/reference/algorithms/shortest_paths/>
7. **Ruff**: <https://docs.astral.sh/ruff/>
8. **FastAPI на зафиксированном коммите**: <https://github.com/fastapi/fastapi/tree/95f8322>

Для старта Tree-sitter достаточно получить `Tree` и посмотреть `Node.type`, дочерние узлы и поля.
Остальное можно осваивать по мере необходимости.

---

## Главное

Хорошее решение:

- надежно отвечает на явно поддержанный класс вопросов;
- работает на реальном популярном репозитории;
- не скрывает неопределенность анализа.

Для инженерного агента честное `unresolved` обычно полезнее убедительно выглядящего неправильного
ответа.
