from app.todos import TodoStore


def test_get_non_existent_todo_raises_key_error():
    store = TodoStore()
    with pytest.raises(KeyError) as exc_info:
        store.get(1)
    assert exc_info.value == KeyError('Todo with id 1 not found')


def test_update_non_existent_todo_raises_key_error():
    store = TodoStore()
    with pytest.raises(KeyError) as exc_info:
        store.update(1, title='Buy groceries and milk')
    assert exc_info.value == KeyError('Todo with id 1 not found')


def test_delete_non_existent_todo_raises_key_error():
    store = TodoStore()
    with pytest.raises(KeyError) as exc_info:
        store.delete(1)
    assert exc_info.value == KeyError('Todo with id 1 not found')