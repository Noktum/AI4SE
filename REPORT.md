# Отчет

## 1. Представление

Индекс строится по каталогу пакета: имя каталога становится пакетом верхнего уровня. Для каждого .py файла (кроме скрытых каталогов и __pycache__) хранятся:

- модуль (kind: module, line = 1);
- классы, функции и методы с canonical qualified name;
- imports всех шести форм с файлом, строкой и scope;
- call sites: выражение вызова, файл, строка, ближайший scope и результат разрешения;
- references: импорты и разрешенные вызовы;
- направленный call graph на NetworkX.

Qualified name - это имя модуля плюс цепочка вложенных определений:
fastapi.applications.FastAPI.setup.openapi. Scope вызова - ближайшая функция/метод, иначе класс, иначе модуль. Строки 1-based; для декорированной функции берется строка def, а не декоратора. Дубли определений в ветках if/try сохраняются списком.

## 2. Разрешение имен

Поддержаны правила:

| правило | пример | результат |
|---|---|---|
| имя из того же модуля | leaf() | rules_pkg.target.leaf |
| вложенная функция | inner() в outer.caller | rules_pkg.target.outer.inner |
| from + alias + relative | from .target import leaf as run_leaf | rules_pkg.target.leaf |
| from . import module | relative_target.leaf() | rules_pkg.target.leaf |
| import pkg.mod as alias | target.leaf() | rules_pkg.target.leaf |
| import pkg.mod | rules_pkg.target.leaf() | rules_pkg.target.leaf |
| from ..module import symbol | from ..target import leaf | rules_pkg.target.leaf |
| re-export цепочкой | rules_pkg.leaf через hub.py | rules_pkg.target.leaf |
| вызов класса | Widget() | rules_pkg.target.Widget |
| self.method() | self.helper() | ...Widget.helper |
| shadowing | def f(leaf): leaf() | unresolved, не target.leaf |

External-вызовы (например, json.dumps) получают статус external. Если имя перекрыто параметром или простым присваиванием, вызов не разрешается в одноименную функцию модуля. Builtins относятся к external (builtins.len).

Осознанно не разрешаются: type inference, произвольный obj.method(), методы базовых классов, super()/cls.method(), self внутри вложенной функции, imports внутри функций, getattr, import *, monkey patching и перекрытие имени присваиванием, dependency injection FastAPI.

## 3. Ограничение

fastapi/routing.py:352:

```python
return await dependant.call(**values)
```

Вызов остается unresolved с причиной dynamic receiver: dependant - параметр функции run_endpoint_function, а call - атрибут объекта Dependant, который заполняется во время выполнения. В индексе нет типов и data-flow, поэтому нельзя понять, что dependant.call ссылается на endpoint-функцию. Для корректного ответа понадобился бы вывод типов (или аннотации + анализ полей класса) и учет того, как FastAPI заполняет Dependant при регистрации маршрута. Похожая ситуация - self.router._get_routes_version в FastAPI.openapi: self.router имеет динамический тип, поэтому вызов честно помечен unresolved.

## 4. Использование AI

Реализация RepoIndex и CallGraph, а также тесты сделаны с помощью ИИ агента исходя из ASSIGNMENT.md. Самостоятельно проверялись публичные smoke-тесты на FastAPI, выводы на tiny_pkg и синтетическом fixture. После проверки исправлены двойная регистрация методов класса как функций модуля (сравнение узлов Tree-sitter по id, а не по identity), строка определения у декорированных функций, различие причин local variable/dynamic receiver и обработка self только в непосредственном методе класса. Ограничения анализа проверялись на примерах из rules_pkg/limits.py - они должны оставаться unresolved и не давать ложных ребер.
