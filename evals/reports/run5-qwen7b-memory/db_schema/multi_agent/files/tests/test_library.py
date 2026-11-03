from app.library import add_author, add_book, books_by, delete_author
import pytest
import os

@pytest.fixture(autouse=True)
def clean_database():
    from sqlalchemy import create_engine, text
    engine = create_engine(os.environ.get('DATABASE_URL', 'sqlite:///test.db'))
    with engine.connect() as conn:
        conn.execute(text('TRUNCATE authors, books RESTART IDENTITY CASCADE'))


def test_add_author():
    author_id = add_author('John Doe')
    assert author_id == 1
    with pytest.raises(ValueError):
        add_author('John Doe')


def test_add_book():
    author_id = add_author('John Doe')
    book_id = add_book(author_id, 'Book Title', 2000)
    assert book_id == 1
    with pytest.raises(ValueError):
        add_book(author_id, 'Book Title', 1400)
    with pytest.raises(ValueError):
        add_book(2, 'Book Title', 2000)


def test_books_by():
    author_id = add_author('John Doe')
    add_book(author_id, 'Book Title 1', 2000)
    add_book(author_id, 'Book Title 2', 1900)
    books = books_by(author_id)
    assert books == ['Book Title 1', 'Book Title 2']


def test_delete_author():
    author_id = add_author('John Doe')
    add_book(author_id, 'Book Title', 2000)
    delete_author(author_id)
    with pytest.raises(ValueError):
        books_by(author_id)