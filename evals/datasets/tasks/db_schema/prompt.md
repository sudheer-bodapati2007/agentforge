Build a small library catalogue backed by the PostgreSQL database.

Schema (write it as a SQL migration):
- table `authors` with columns `id` (primary key) and `name` (text, required, unique);
- table `books` with columns `id` (primary key), `author_id` (required, references `authors`),
  `title` (text, required) and `year` (integer, required, must be greater than 1400).
  Deleting an author deletes their books.
The database itself must enforce these rules (constraints), not only the Python code.

In `app/library.py` write:
- `add_author(name: str) -> int` returns the new author's id; raises `ValueError` if an author
  with that name already exists;
- `add_book(author_id: int, title: str, year: int) -> int` returns the new book's id; raises
  `ValueError` if the author does not exist or the year is not greater than 1400;
- `books_by(author_id: int) -> list[str]` returns the author's book titles ordered by year,
  then title;
- `delete_author(author_id: int) -> None` deletes the author and their books.
