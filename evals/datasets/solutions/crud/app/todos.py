class TodoStore:
    def __init__(self) -> None:
        self._todos: dict[int, dict] = {}
        self._next_id = 1

    @staticmethod
    def _clean(title: str) -> str:
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must not be empty")
        return title.strip()

    def _find(self, todo_id: int) -> dict:
        if todo_id not in self._todos:
            raise KeyError(todo_id)
        return self._todos[todo_id]

    def add(self, title: str) -> dict:
        todo = {"id": self._next_id, "title": self._clean(title), "done": False}
        self._todos[todo["id"]] = todo
        self._next_id += 1
        return dict(todo)

    def get(self, todo_id: int) -> dict:
        return dict(self._find(todo_id))

    def list(self) -> list[dict]:
        return [dict(self._todos[key]) for key in sorted(self._todos)]

    def update(self, todo_id: int, title: str | None = None, done: bool | None = None) -> dict:
        todo = self._find(todo_id)
        new_title = self._clean(title) if title is not None else todo["title"]
        todo["title"] = new_title
        if done is not None:
            todo["done"] = done
        return dict(todo)

    def delete(self, todo_id: int) -> None:
        self._find(todo_id)
        del self._todos[todo_id]
