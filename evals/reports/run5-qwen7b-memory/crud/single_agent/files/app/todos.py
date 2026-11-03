from typing import Dict, Optional


class TodoStore:
    def __init__(self):
        self.todos: Dict[int, Dict[str, str | bool]] = {}
        self.next_id: int = 1

    def add(self, title: str) -> Dict[str, str | bool]:
        title = title.strip()
        if not title:
            raise ValueError('Title cannot be empty or only whitespace')
        todo = {'id': self.next_id, 'title': title, 'done': False}
        self.todos[self.next_id] = todo
        self.next_id += 1
        return todo.copy()

    def get(self, todo_id: int) -> Dict[str, str | bool]:
        if todo_id not in self.todos:
            raise KeyError('Todo not found')
        return self.todos[todo_id].copy()

    def list(self) -> list[Dict[str, str | bool]]:
        return list(self.todos.values())

    def update(self, todo_id: int, title: Optional[str] = None, done: Optional[bool] = None) -> Dict[str, str | bool]:
        if todo_id not in self.todos:
            raise KeyError('Todo not found')
        todo = self.todos[todo_id]
        if title is not None:
            todo['title'] = title.strip()
            if not todo['title']:
                raise ValueError('Title cannot be empty or only whitespace')
        if done is not None:
            todo['done'] = done
        return todo.copy()

    def delete(self, todo_id: int) -> None:
        if todo_id not in self.todos:
            raise KeyError('Todo not found')
        del self.todos[todo_id]
