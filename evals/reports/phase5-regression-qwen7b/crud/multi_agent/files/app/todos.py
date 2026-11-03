class TodoStore:
    def __init__(self):
        self._todos = {}
        self._next_id = 1

    def add(self, title: str) -> dict:
        title = title.strip()
        if not title:
            raise ValueError('Title cannot be empty or only whitespace')
        todo = {'id': self._next_id, 'title': title, 'done': False}
        self._todos[self._next_id] = todo
        self._next_id += 1
        return todo

    def get(self, todo_id: int) -> dict:
        if todo_id not in self._todos:
            raise KeyError('Todo not found')
        return self._todos[todo_id].copy()

    def list(self) -> list[dict]:
        return list(self._todos.values())

    def update(self, todo_id: int, title: str | None = None, done: bool | None = None) -> dict:
        if todo_id not in self._todos:
            raise KeyError('Todo not found')
        todo = self._todos[todo_id]
        if title is not None:
            todo['title'] = title.strip()
            if not todo['title']:
                raise ValueError('Title cannot be empty or only whitespace')
        if done is not None:
            todo['done'] = done
        return todo.copy()

    def delete(self, todo_id: int) -> None:
        if todo_id not in self._todos:
            raise KeyError('Todo not found')
        del self._todos[todo_id]
        # Reset the next_id if it's greater than the deleted id
        if todo_id == self._next_id - 1:
            self._next_id -= 1