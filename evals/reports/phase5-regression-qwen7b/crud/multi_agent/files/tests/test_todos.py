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


def test_list_todos():
    store = TodoStore()
    store.add('Buy groceries')
    store.add('Clean the house')
    todos = store.list()
    assert todos == [{'id': 1, 'title': 'Buy groceries', 'done': False}, {'id': 2, 'title': 'Clean the house', 'done': False}]


def test_update_todo():
    store = TodoStore()
    store.add('Buy groceries')
    todo = store.update(1, title='Buy milk', done=True)
    assert todo == {'id': 1, 'title': 'Buy milk', 'done': True}


def test_delete_todo():
    store = TodoStore()
    store.add('Buy groceries')
    store.delete(1)
    assert store.list() == []


def test_get_nonexistent_todo():
    store = TodoStore()
    with pytest.raises(KeyError):
        store.get(1)


def test_update_nonexistent_todo():
    store = TodoStore()
    with pytest.raises(KeyError):
        store.update(1)


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


def test_update_title_to_empty():
    store = TodoStore()
    store.add('Buy groceries')
    with pytest.raises(ValueError):
        store.update(1, title='   ')


def test_update_title_to_whitespace():
    store = TodoStore()
    store.add('Buy groceries')
    with pytest.raises(ValueError):
        store.update(1, title='   ')


def test_update_done_status():
    store = TodoStore()
    store.add('Buy groceries')
    todo = store.update(1, done=True)
    assert todo == {'id': 1, 'title': 'Buy groceries', 'done': True}


def test_update_multiple_fields():
    store = TodoStore()
    store.add('Buy groceries')
    todo = store.update(1, title='Buy milk', done=True)
    assert todo == {'id': 1, 'title': 'Buy milk', 'done': True}


def test_update_no_changes():
    store = TodoStore()
    store.add('Buy groceries')
    todo = store.update(1)
    assert todo == {'id': 1, 'title': 'Buy groceries', 'done': False}


def test_add_duplicate_id():
    store = TodoStore()
    store.add('Buy groceries')
    store.delete(1)
    todo = store.add('Buy groceries')
    assert todo == {'id': 1, 'title': 'Buy groceries', 'done': False}
