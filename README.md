# repo-map

Индекс Python-репозитория на Tree-sitter: определения, imports, вызовы и пять запросов
к приближенному call graph.

## Запуск

```bash
uv sync
uv run repo-map --help
```

FastAPI для проверок клонируется рядом с репозиторием:

```text
work/
├── repo-map-starter/   этот репозиторий
└── fastapi/
    └── fastapi/        <- --root
```

## Запросы

Во всех примерах `--root ../fastapi/fastapi`.

```bash
uv run repo-map definition fastapi.FastAPI --root ../fastapi/fastapi
```

```json
{
  "query": "definition",
  "input": "fastapi.FastAPI",
  "symbol": "fastapi.applications.FastAPI",
  "results": [
    {"qualified_name": "fastapi.applications.FastAPI", "kind": "class",
     "file": "fastapi/applications.py", "line": 42, "async": false}
  ]
}
```

```bash
uv run repo-map references fastapi.openapi.utils.get_openapi --root ../fastapi/fastapi
uv run repo-map callers    fastapi.openapi.utils.get_openapi --root ../fastapi/fastapi
uv run repo-map callees    fastapi.applications.FastAPI.openapi --root ../fastapi/fastapi
uv run repo-map path fastapi.applications.FastAPI.openapi \
    fastapi.openapi.utils.get_openapi_path --root ../fastapi/fastapi
```

`references` возвращает импорты (`kind: import`) и разрешенные вызовы (`kind: call`);
`callers` — определения вызывающих символов; `callees` делит вызовы на `results`
(внутри проекта), `external` и `unresolved`; `path` — кратчайший путь в графе или `null`.

## Формат JSON

Формат полностью соответствует условию: дополнительные поля не добавлялись.
Имена в ответе всегда canonical (по месту определения), даже если запрос использовал
alias или re-export. Причина unresolved (`reason`) — короткая строка: `local variable`,
`dynamic receiver`, `not defined in class`, `unknown name`, `module is not callable`.

## Проверки

```bash
uv run pytest -q
uv run pytest -q -m fastapi   # нужен ../fastapi
uv run ruff check .
uv run ruff format --check .
```

Свои тесты лежат в `tests/test_rules.py` и `tests/test_fixture_queries.py`; fixture
`tests/fixtures/rules_pkg/` покрывает обязательные правила разрешения имен и случаи,
которые должны остаться unresolved.
