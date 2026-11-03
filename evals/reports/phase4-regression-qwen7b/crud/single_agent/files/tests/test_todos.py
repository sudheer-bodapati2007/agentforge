import pytest
from app.todos import TodoStore


@pytest.fixture
def todo_store():
    return TodoStore()


def test_add(todo_store):
    todo = todo_store.add('Buy groceries')
    assert todo == {'id': 1, 'title': 'Buy groceries', 'done': False}


def test_get(todo_store):
    todo = todo_store.add('Buy groceries')
    retrieved_todo = todo_store.get(todo['id'])
    assert retrieved_todo == {'id': 1, 'title': 'Buy groceries', 'done': False}


def test_list(todo_store):
    todo1 = todo_store.add('Buy groceries')
    todo2 = todo_store.add('Clean house')
    todos = todo_store.list()
    assert todos == [{'id': 1, 'title': 'Buy groceries', 'done': False}, {'id': 2, 'title': 'Clean house', 'done': False}]


def test_update(todo_store):
    todo = todo_store.add('Buy groceries')
    updated_todo = todo_store.update(todo['id'], title='Buy milk', done=True)
    assert updated_todo == {'id': 1, 'title': 'Buy milk', 'done': True}


def test_delete(todo_store):
    todo = todo_store.add('Buy groceries')
    todo_store.delete(todo['id'])
    with pytest.raises(KeyError):
        todo_store.get(todo['id'])


def test_add_invalid_title(todo_store):
    with pytest.raises(ValueError):
        todo_store.add('   ')


def test_update_invalid_title(todo_store):
    todo = todo_store.add('Buy groceries')
    with pytest.raises(ValueError):
        todo_store.update(todo['id'], title='   ')


def test_get_nonexistent_id(todo_store):
    with pytest.raises(KeyError):
        todo_store.get(1)


def test_update_nonexistent_id(todo_store):
    with pytest.raises(KeyError):
        todo_store.update(1)


def test_delete_nonexistent_id(todo_store):
    with pytest.raises(KeyError):
        todo_store.delete(1)
