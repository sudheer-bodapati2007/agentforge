import pytest
from app.library import add_author, add_book, books_by, delete_author

@pytest.fixture(autouse=True)
def clean_db():
    from sqlalchemy import create_engine, MetaData
    engine = create_engine(os.environ.get('DATABASE_URL', 'sqlite:///test.db'))
    metadata = MetaData(bind=engine)
    metadata.reflect()
    for table in reversed(metadata.sorted_tables):
        engine.execute(table.delete())

def test_add_author():
    author_id = add_author('John Doe')
    assert author_id > 0

    with pytest.raises(ValueError) as e:
        add_author('John Doe')
    assert 'Author already exists' in str(e.value)

def test_add_book():
    author_id = add_author('John Doe')
    book_id = add_book(author_id, 'Book Title', 2020)
    assert book_id > 0

    with pytest.raises(ValueError) as e:
        add_book(author_id, 'Book Title', 1400)
    assert 'Invalid book data' in str(e.value)

    with pytest.raises(ValueError) as e:
        add_book(999, 'Book Title', 2020)
    assert 'Author does not exist' in str(e.value)

def test_books_by():
    author_id = add_author('John Doe')
    add_book(author_id, 'Book Title 1', 2020)
    add_book(author_id, 'Book Title 2', 2019)
    books = books_by(author_id)
    assert books == ['Book Title 2', 'Book Title 1']

    books = books_by(999)
    assert books == []

def test_delete_author():
    author_id = add_author('John Doe')
    add_book(author_id, 'Book Title', 2020)
    delete_author(author_id)

    books = books_by(author_id)
    assert books == []

    with pytest.raises(ValueError) as e:
        delete_author(author_id)
    assert 'Author does not exist' in str(e.value)