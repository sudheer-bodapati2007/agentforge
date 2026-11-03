# REST API guidelines

## Versioning
Every route is prefixed with the major version, for example `/v1/orders`. Breaking changes ship
under a new version; the previous version keeps working for at least six months.

## Status codes
Creating a resource returns 201 with a Location header. A missing resource returns 404.
Validation failures return 422. A request that conflicts with the current state, such as
cancelling an order that has already shipped, returns 409.

## Pagination
Collection endpoints accept `limit` and `cursor` query parameters. The default page size is 25
and the largest allowed limit is 200. Responses include `next_cursor`, which is null on the
last page. Offset-based pagination is not allowed because it skips rows under concurrent writes.

## Error format
Error bodies always have the shape `{"error": {"code": ..., "message": ...}}`. The code is a
stable machine-readable string; the message is for humans and may change.

## Idempotency
POST endpoints that create orders or payments require an `Idempotency-Key` header. Repeating a
request with the same key within 24 hours returns the original response instead of creating a
duplicate.

## Rate limits
Each API key may send 600 requests per minute. Over the limit the API answers 429 with a
Retry-After header that says how many seconds to wait.
