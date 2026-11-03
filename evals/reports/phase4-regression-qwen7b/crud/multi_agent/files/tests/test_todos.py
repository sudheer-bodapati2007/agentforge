from app.todos import TodoStore
import pytest


def test_add_todo():
    store = TodoStore()
    todo = store.add('Buy groceries')
    assert todo == {'id': 1, 'title': 'Buy groceries', 'done': False}


def test_get_todo():
    store = TodoStore()
    store.add('Buy groceries')
    todo = store.get(1)
    assert todo == {'id': 1, 'title': 'Buy groceries', 'done': False}


def test_get_nonexistent_todo():
    store = TodoStore()
    with pytest.raises(KeyError):
        store.get(1)


def test_list_todos():
    store = TodoStore()
    store.add('Buy groceries')
    store.add('Do laundry')
    todos = store.list()
    assert todos == [{'id': 1, 'title': 'Buy groceries', 'done': False}, {'id': 2, 'title': 'Do laundry', 'done': False}]


def test_update_todo():
    store = TodoStore()
    store.add('Buy groceries')
    updated_todo = store.update(1, title='Buy milk', done=True)
    assert updated_todo == {'id': 1, 'title': 'Buy milk', 'done': True}


def test_update_nonexistent_todo():
    store = TodoStore()
    with pytest.raises(KeyError):
        store.update(1, title='Buy milk')


def test_delete_todo():
    store = TodoStore()
    store.add('Buy groceries')
    store.delete(1)
    with pytest.raises(KeyError):
        store.get(1)


def test_delete_nonexistent_todo():
    store = TodoStore()
    with pytest.raises(KeyError):
        store.delete(1)


def test_add_empty_title():
    store = TodoStore()
    with pytest.raises(ValueError):
        store.add('   ')


def test_update_empty_title():
    store = TodoStore()
    store.add('Buy groceries')
    with pytest.raises(ValueError):
        store.update(1, title='   ')