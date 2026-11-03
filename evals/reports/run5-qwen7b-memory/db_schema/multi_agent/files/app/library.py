from sqlalchemy import create_engine, text, select, delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import os

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///test.db')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def add_author(name: str) -> int:
    with Session() as session:
        try:
            session.execute(text('INSERT INTO authors (name) VALUES (:name) RETURNING id'), {'name': name})
            session.commit()
            return session.execute(text('SELECT id FROM authors WHERE name = :name'), {'name': name}).scalar()
        except IntegrityError:
            raise ValueError('Author with that name already exists')


def add_book(author_id: int, title: str, year: int) -> int:
    with Session() as session:
        if session.execute(text('SELECT 1 FROM authors WHERE id = :author_id'), {'author_id': author_id}).scalar() is None:
            raise ValueError('Author does not exist')
        if year <= 1400:
            raise ValueError('Year must be greater than 1400')
        session.execute(text('INSERT INTO books (author_id, title, year) VALUES (:author_id, :title, :year) RETURNING id'), {'author_id': author_id, 'title': title, 'year': year})
        session.commit()
        return session.execute(text('SELECT id FROM books WHERE author_id = :author_id AND title = :title AND year = :year'), {'author_id': author_id, 'title': title, 'year': year}).scalar()


def books_by(author_id: int) -> list[str]:
    with Session() as session:
        books = session.execute(text('SELECT title FROM books WHERE author_id = :author_id ORDER BY year, title'), {'author_id': author_id}).fetchall()
        return [book[0] for book in books]


def delete_author(author_id: int) -> None:
    with Session() as session:
        session.execute(text('DELETE FROM books WHERE author_id = :author_id'), {'author_id': author_id})
        session.execute(text('DELETE FROM authors WHERE id = :author_id'), {'author_id': author_id})
        session.commit()