from app.todos import TodoStore

def test_add_todo():
    store = TodoStore()
    todo = store.add('Buy groceries')
    assert todo == {'id': 1, 'title': 'Buy groceries', 'done': False}

    todo = store.add('Read a book')
    assert todo == {'id': 2, 'title': 'Read a book', 'done': False}

    assert store.list() == [{'id': 1, 'title': 'Buy groceries', 'done': False}, {'id': 2, 'title': 'Read a book', 'done': False}]


def test_get_todo():
    store = TodoStore()
    store.add('Buy groceries')
    todo = store.get(1)
    assert todo == {'id': 1, 'title': 'Buy groceries', 'done': False}


def test_update_todo():
    store = TodoStore()
    store.add('Buy groceries')
    todo = store.update(1, title='Buy milk')
    assert todo == {'id': 1, 'title': 'Buy milk', 'done': False}

    todo = store.update(1, done=True)
    assert todo == {'id': 1, 'title': 'Buy milk', 'done': True}


def test_delete_todo():
    store = TodoStore()
    store.add('Buy groceries')
    store.delete(1)
    assert store.list() == []


def test_error_add_empty_title():
    store = TodoStore()
    with pytest.raises(ValueError):
        store.add('   ')


def test_error_update_empty_title():
    store = TodoStore()
    store.add('Buy groceries')
    with pytest.raises(ValueError):
        store.update(1, title='   ')


def test_error_get_nonexistent_id():
    store = TodoStore()
    with pytest.raises(KeyError):
        store.get(1)


def test_error_update_nonexistent_id():
    store = TodoStore()
    with pytest.raises(KeyError):
        store.update(1)


def test_error_delete_nonexistent_id():
    store = TodoStore()
    with pytest.raises(KeyError):
        store.delete(1)