"""Hidden reference tests for the crud task."""

import pytest

from app.todos import TodoStore


def test_add_returns_new_todo():
    store = TodoStore()
    assert store.add("  Buy milk ") == {"id": 1, "title": "Buy milk", "done": False}


def test_ids_start_at_one_per_store():
    first, second = TodoStore(), TodoStore()
    first.add("a")
    first.add("b")
    assert second.add("c")["id"] == 1


def test_ids_are_never_reused():
    store = TodoStore()
    store.add("a")
    second = store.add("b")["id"]
    store.delete(second)
    assert store.add("c")["id"] == second + 1


def test_get_and_list():
    store = TodoStore()
    a = store.add("a")
    b = store.add("b")
    assert store.get(b["id"]) == b
    assert store.list() == [a, b]


def test_empty_store_lists_nothing():
    assert TodoStore().list() == []


def test_update_changes_only_given_fields():
    store = TodoStore()
    todo = store.add("write report")
    assert store.update(todo["id"], done=True) == {"id": todo["id"], "title": "write report", "done": True}
    assert store.update(todo["id"], title=" final report ") == {"id": todo["id"], "title": "final report", "done": True}
    assert store.get(todo["id"])["done"] is True


def test_delete_removes():
    store = TodoStore()
    todo = store.add("x")
    assert store.delete(todo["id"]) is None
    assert store.list() == []
    with pytest.raises(KeyError):
        store.get(todo["id"])


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
def test_unknown_id_is_key_error(operation):
    store = TodoStore()
    with pytest.raises(KeyError):
        getattr(store, operation)(42)


@pytest.mark.parametrize("title", ["", "   "])
def test_blank_title_on_add(title):
    with pytest.raises(ValueError):
        TodoStore().add(title)


def test_blank_title_on_update_keeps_old_title():
    store = TodoStore()
    todo = store.add("keep")
    with pytest.raises(ValueError):
        store.update(todo["id"], title="  ")
    assert store.get(todo["id"])["title"] == "keep"


def test_returned_dicts_are_copies():
    store = TodoStore()
    todo = store.add("original")
    todo["title"] = "changed"
    store.get(1)["done"] = True
    store.list()[0]["title"] = "also changed"
    assert store.get(1) == {"id": 1, "title": "original", "done": False}
