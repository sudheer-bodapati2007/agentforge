from typing import Dict, Optional


class TodoStore:
    def __init__(self):
        self.todos: Dict[int, Dict[str, str]] = {}
        self.next_id: int = 1

    def add(self, title: str) -> Dict[str, str]:
        if not title.strip():
            raise ValueError('Title cannot be empty or only whitespace')
        todo = {'id': self.next_id, 'title': title.strip()}
        self.todos[self.next_id] = todo
        self.next_id += 1
        return todo.copy()

    def get(self, todo_id: int) -> Dict[str, str]:
        if todo_id not in self.todos:
            raise KeyError(f'Todo with id {todo_id} not found')
        return self.todos[todo_id].copy()

    def list(self) -> list[Dict[str, str]]:
        return list(self.todos.values())

    def update(self, todo_id: int, title: Optional[str] = None) -> Dict[str, str]:
        if todo_id not in self.todos:
            raise KeyError(f'Todo with id {todo_id} not found')
        todo = self.todos[todo_id]
        if title is not None:
            todo['title'] = title.strip()
        return todo.copy()

    def delete(self, todo_id: int) -> None:
        if todo_id not in self.todos:
            raise KeyError(f'Todo with id {todo_id} not found')
        del self.todos[todo_id]
