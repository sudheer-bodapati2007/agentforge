from app.todos import TodoStore
import pytest


def test_add_todo():
    store = TodoStore()
    todo = store.add('Buy groceries')
    assert todo == {'id': 1, 'title': 'Buy groceries', 'done': False}
    assert store.todos == {1: {'id': 1, 'title': 'Buy groceries', 'done': False}}


def test_add_todo_with_whitespace():
    store = TodoStore()
    todo = store.add('  Buy groceries  ')
    assert todo == {'id': 1, 'title': 'Buy groceries', 'done': False}
    assert store.todos == {1: {'id': 1, 'title': 'Buy groceries', 'done': False}}


def test_add_todo_with_empty_title():
    store = TodoStore()
    with pytest.raises(ValueError) as exc_info:
        store.add('')
    assert str(exc_info.value) == 'Title cannot be empty or only whitespace'


def test_get_todo():
    store = TodoStore()
    store.add('Buy groceries')
    todo = store.get(1)
    assert todo == {'id': 1, 'title': 'Buy groceries', 'done': False}
    assert store.todos == {1: {'id': 1, 'title': 'Buy groceries', 'done': False}}


def test_get_non_existent_todo():
    store = TodoStore()
    with pytest.raises(KeyError) as exc_info:
        store.get(1)
    assert str(exc_info.value) == 'Todo not found'


def test_list_todos():
    store = TodoStore()
    store.add('Buy groceries')
    store.add('Do laundry')
    todos = store.list()
    assert todos == [{'id': 1, 'title': 'Buy groceries', 'done': False}, {'id': 2, 'title': 'Do laundry', 'done': False}]
    assert store.todos == {1: {'id': 1, 'title': 'Buy groceries', 'done': False}, 2: {'id': 2, 'title': 'Do laundry', 'done': False}}


def test_update_todo():
    store = TodoStore()
    store.add('Buy groceries')
    todo = store.update(1, title='Buy milk')
    assert todo == {'id': 1, 'title': 'Buy milk', 'done': False}
    assert store.todos == {1: {'id': 1, 'title': 'Buy milk', 'done': False}}


def test_update_non_existent_todo():
    store = TodoStore()
    with pytest.raises(KeyError) as exc_info:
        store.update(1)
    assert str(exc_info.value) == 'Todo not found'


def test_update_with_none_title():
    store = TodoStore()
    store.add('Buy groceries')
    todo = store.update(1, title=None)
    assert todo == {'id': 1, 'title': 'Buy groceries', 'done': False}
    assert store.todos == {1: {'id': 1, 'title': 'Buy groceries', 'done': False}}


def test_update_with_none_done():
    store = TodoStore()
    store.add('Buy groceries')
    todo = store.update(1, done=None)
    assert todo == {'id': 1, 'title': 'Buy groceries', 'done': False}
    assert store.todos == {1: {'id': 1, 'title': 'Buy groceries', 'done': False}}


def test_delete_todo():
    store = TodoStore()
    store.add('Buy groceries')
    store.delete(1)
    assert store.todos == {}


def test_delete_non_existent_todo():
    store = TodoStore()
    with pytest.raises(KeyError) as exc_info:
        store.delete(1)
    assert str(exc_info.value) == 'Todo not found'


def test_todo_copies():
    store = TodoStore()
    todo = store.add('Buy groceries')
    todo['title'] = 'Buy milk'
    assert store.todos == {1: {'id': 1, 'title': 'Buy groceries', 'done': False}}


def test_id_not_reused():
    store = TodoStore()
    store.add('Buy groceries')
    store.delete(1)
    todo = store.add('Do laundry')
    assert todo == {'id': 2, 'title': 'Do laundry', 'done': False}
    assert store.todos == {2: {'id': 2, 'title': 'Do laundry', 'done': False}}