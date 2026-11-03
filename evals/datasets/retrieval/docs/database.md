# Database practices

## Migrations
Schema changes are Alembic migrations reviewed like code. A migration must be reversible and must
not lock a large table: add columns as nullable first, backfill in batches, then add the
constraint in a later release.

## Transactions
Keep transactions short and never call an external HTTP service while a transaction is open. Use
`SELECT ... FOR UPDATE SKIP LOCKED` when several workers take jobs from the same queue table.

## Soft deletes
Orders and customers are never physically deleted. Set `deleted_at` to the current UTC time and
filter it out in every query; a nightly job purges soft-deleted rows after 90 days to meet the
data retention policy.

## Indexes
Every foreign key gets an index. Add a composite index when a query filters on one column and
sorts on another, with the filter column first.

## Connection pooling
Each service instance uses a pool of at most 10 connections. Long-running reports go to the read
replica, never to the primary database.
