from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, select, delete
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
import os

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///test.db')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Author(Base):
    __tablename__ = 'authors'
    id = Column(Integer, primary_key=True)
    name = Column(String, required=True, unique=True)

    books = relationship('Book', back_populates='author', cascade='all, delete-orphan')

class Book(Base):
    __tablename__ = 'books'
    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey('authors.id'), required=True)
    title = Column(String, required=True)
    year = Column(Integer, required=True, check_constraint='year > 1400')

    author = relationship('Author', back_populates='books')

Base.metadata.create_all(engine)

def add_author(name: str) -> int:
    session = Session()
    try:
        author = Author(name=name)
        session.add(author)
        session.commit()
        return author.id
    except Exception as e:
        session.rollback()
        raise ValueError(f'Author already exists: {e}')

def add_book(author_id: int, title: str, year: int) -> int:
    session = Session()
    try:
        author = session.get(Author, author_id)
        if not author:
            raise ValueError('Author does not exist')
        book = Book(author=author, title=title, year=year)
        session.add(book)
        session.commit()
        return book.id
    except Exception as e:
        session.rollback()
        raise ValueError(f'Invalid book data: {e}')

def books_by(author_id: int) -> list[str]:
    session = Session()
    try:
        author = session.get(Author, author_id)
        if not author:
            return []
        return [book.title for book in author.books.order_by(Book.year, Book.title)]
    except Exception as e:
        raise ValueError(f'Invalid author ID: {e}')

def delete_author(author_id: int) -> None:
    session = Session()
    try:
        author = session.get(Author, author_id)
        if not author:
            raise ValueError('Author does not exist')
        session.delete(author)
        session.commit()
    except Exception as e:
        session.rollback()
        raise ValueError(f'Error deleting author: {e}')