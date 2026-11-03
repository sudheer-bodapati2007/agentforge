# Security requirements

## Authentication
Clients authenticate with short-lived JWT access tokens (15 minutes) signed with RS256. Refresh
tokens last 30 days and are rotated every time they are used. Service-to-service calls use mutual
TLS instead of tokens.

## Passwords
Passwords are hashed with Argon2id using the library defaults. Never store or log plain text
passwords, and never compare password hashes with `==`; use the library's constant-time verify.

## Secrets
API keys, database passwords and signing keys come from the secret manager at startup. They are
never committed to git, never placed in Docker images and never passed on a command line.

## Input validation
Validate every request body with a Pydantic model at the edge of the service. Reject unknown
fields. Treat file names supplied by users as untrusted: strip directory parts before using them.

## CORS
Browsers may call the API only from the dashboard origins listed in configuration. Wildcard
origins are not allowed in production.
