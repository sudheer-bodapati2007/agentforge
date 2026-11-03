"""Hidden reference tests for the db_schema task. Run against a real PostgreSQL with the
system's migrations applied. They check the Python API and that the database itself
enforces the rules (raw SQL that breaks a rule must fail)."""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.library import add_author, add_book, books_by, delete_author

engine = create_engine(os.environ["DATABASE_URL"])


@pytest.fixture(autouse=True)
def clean():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE books, authors RESTART IDENTITY CASCADE"))


def raw(sql: str, **params):
    with engine.begin() as conn:
        conn.execute(text(sql), params)


def test_add_and_list_books_in_year_then_title_order():
    author = add_author("Le Guin")
    add_book(author, "The Lathe of Heaven", 1971)
    add_book(author, "The Dispossessed", 1974)
    add_book(author, "A Wizard of Earthsea", 1968)
    add_book(author, "City of Illusions", 1967)
    assert books_by(author) == ["City of Illusions", "A Wizard of Earthsea", "The Lathe of Heaven", "The Dispossessed"]


def test_ties_on_year_are_ordered_by_title():
    author = add_author("Anon")
    add_book(author, "Zebra", 2000)
    add_book(author, "Apple", 2000)
    assert books_by(author) == ["Apple", "Zebra"]


def test_books_belong_to_their_author_only():
    a, b = add_author("A"), add_author("B")
    add_book(a, "Mine", 2001)
    assert books_by(b) == []


def test_duplicate_author_is_a_value_error():
    add_author("Butler")
    with pytest.raises(ValueError):
        add_author("Butler")


def test_unknown_author_is_a_value_error():
    with pytest.raises(ValueError):
        add_book(999, "Orphan", 2000)


@pytest.mark.parametrize("year", [1400, 1000, -5])
def test_invalid_year_is_a_value_error(year):
    author = add_author("X")
    with pytest.raises(ValueError):
        add_book(author, "Old", year)


def test_deleting_an_author_deletes_their_books():
    author = add_author("Gone")
    add_book(author, "Lost", 1999)
    delete_author(author)
    assert books_by(author) == []
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM books")).scalar_one() == 0


def test_the_database_enforces_unique_author_names():
    raw("INSERT INTO authors (name) VALUES ('Same')")
    with pytest.raises(IntegrityError):
        raw("INSERT INTO authors (name) VALUES ('Same')")


def test_the_database_enforces_the_year_rule():
    raw("INSERT INTO authors (name) VALUES ('Y')")
    with pytest.raises(IntegrityError):
        raw("INSERT INTO books (author_id, title, year) VALUES ((SELECT id FROM authors), 'Old', 1300)")


def test_the_database_enforces_the_author_reference():
    with pytest.raises(IntegrityError):
        raw("INSERT INTO books (author_id, title, year) VALUES (424242, 'Orphan', 2000)")


def test_the_database_cascades_author_deletion():
    raw("INSERT INTO authors (name) VALUES ('Z')")
    raw("INSERT INTO books (author_id, title, year) VALUES ((SELECT id FROM authors), 'B', 2000)")
    raw("DELETE FROM authors")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM books")).scalar_one() == 0


def test_required_columns_are_not_null():
    raw("INSERT INTO authors (name) VALUES ('N')")
    with pytest.raises(IntegrityError):
        raw("INSERT INTO books (author_id, title, year) VALUES ((SELECT id FROM authors), NULL, 2000)")
