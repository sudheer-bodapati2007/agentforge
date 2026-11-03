from app.todos import TodoStore
import pytest


@pytest.fixture
def todo_store():
    return TodoStore()


def test_add(todo_store):
    todo = todo_store.add('Buy milk')
    assert todo == {'id': 1, 'title': 'Buy milk', 'done': False}
    assert todo_store.todos == {1: {'id': 1, 'title': 'Buy milk', 'done': False}}


def test_get(todo_store):
    todo_store.add('Buy milk')
    todo = todo_store.get(1)
    assert todo == {'id': 1, 'title': 'Buy milk', 'done': False}


def test_get_not_found(todo_store):
    with pytest.raises(KeyError):
        todo_store.get(1)


def test_list(todo_store):
    todo_store.add('Buy milk')
    todo_store.add('Buy bread')
    todos = todo_store.list()
    assert todos == [{'id': 1, 'title': 'Buy milk', 'done': False}, {'id': 2, 'title': 'Buy bread', 'done': False}]


def test_update(todo_store):
    todo_store.add('Buy milk')
    todo = todo_store.update(1, title='Buy eggs')
    assert todo == {'id': 1, 'title': 'Buy eggs', 'done': False}
    assert todo_store.todos == {1: {'id': 1, 'title': 'Buy eggs', 'done': False}}


def test_update_not_found(todo_store):
    with pytest.raises(KeyError):
        todo_store.update(1)


def test_update_title_empty(todo_store):
    with pytest.raises(ValueError):
        todo_store.update(1, title='   ')


def test_delete(todo_store):
    todo_store.add('Buy milk')
    todo_store.delete(1)
    assert todo_store.todos == {}


def test_delete_not_found(todo_store):
    with pytest.raises(KeyError):
        todo_store.delete(1)
