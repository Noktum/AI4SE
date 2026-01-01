# repo-map

Индекс Python-репозитория на Tree-sitter: определения, imports, вызовы и пять запросов
к приближенному call graph.

<!-- Заполните разделы ниже. Пишите коротко: это инструкция для того, кто видит проект впервые. -->

## Запуск

```bash
uv sync
uv run repo-map --help
```

## Запросы

<!-- По одному примеру на каждый из пяти запросов, лучше на FastAPI. -->

```bash
uv run repo-map definition fastapi.FastAPI --root ../fastapi/fastapi
```

## Формат JSON

<!-- Базовый формат задан в условии. Опишите, что вы к нему добавили, если добавили. -->

## Проверки

```bash
uv run pytest -q
uv run pytest -q -m fastapi   # публичные smoke tests, нужен ../fastapi
uv run ruff check .
uv run ruff format --check .
```
