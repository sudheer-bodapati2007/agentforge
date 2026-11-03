# Orderly coding standards

These rules apply to every Python service in the Orderly platform.

## Naming
Modules and functions use snake_case. Classes use PascalCase. Module-level constants are
UPPER_SNAKE_CASE. Boolean variables start with is_, has_ or can_ so conditions read naturally.

## Type hints
Every public function has complete type hints, including the return type. Use `X | None`
instead of `Optional[X]`. mypy runs in strict mode in CI and the build fails on any error.

## Errors
Raise specific exceptions: ValueError for invalid arguments, LookupError subclasses for missing
records. Never return None to signal failure, and never catch a bare `except:`. Domain errors
inherit from `OrderlyError` so the API layer can translate them into responses.

## Logging
Use the structured logger from `orderly.logging`, never print(). Log events as key-value pairs,
for example `log.info("order_created", order_id=order.id)`. Personal data such as email
addresses or card numbers must never appear in logs.

## Imports
Group imports as standard library, third party, then first party, separated by blank lines.
Wildcard imports are forbidden.
