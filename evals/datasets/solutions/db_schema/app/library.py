import os

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

engine = create_engine(os.environ["DATABASE_URL"])


def add_author(name: str) -> int:
    try:
        with engine.begin() as conn:
            return conn.execute(text("INSERT INTO authors (name) VALUES (:n) RETURNING id"), {"n": name}).scalar_one()
    except IntegrityError as exc:
        raise ValueError(f"author {name!r} already exists") from exc


def add_book(author_id: int, title: str, year: int) -> int:
    if year <= 1400:
        raise ValueError("year must be greater than 1400")
    try:
        with engine.begin() as conn:
            return conn.execute(
                text("INSERT INTO books (author_id, title, year) VALUES (:a, :t, :y) RETURNING id"),
                {"a": author_id, "t": title, "y": year},
            ).scalar_one()
    except IntegrityError as exc:
        raise ValueError(f"author {author_id} does not exist") from exc


def books_by(author_id: int) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT title FROM books WHERE author_id = :a ORDER BY year, title"), {"a": author_id})
        return [r.title for r in rows]


def delete_author(author_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM authors WHERE id = :a"), {"a": author_id})
