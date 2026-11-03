In `app/todos.py`, write a class `TodoStore` that keeps todos in memory. Each `TodoStore()` instance has its own, initially empty, data.

Methods:
- `add(title: str) -> dict` creates and returns `{"id": int, "title": str, "done": False}`, with the title stripped of surrounding whitespace. Ids start at 1 in every store and increase by 1; the id of a deleted todo is never reused.
- `get(todo_id: int) -> dict` returns the todo.
- `list() -> list[dict]` returns all todos ordered by id.
- `update(todo_id: int, title: str | None = None, done: bool | None = None) -> dict` changes only the arguments that are not None and returns the updated todo.
- `delete(todo_id: int) -> None` removes the todo.

Errors:
- `get`, `update` and `delete` raise `KeyError` for an id that does not exist.
- `add` and `update` raise `ValueError` when a title is empty or only whitespace.

The dicts you return must be copies: changing a returned dict must not change the store.
