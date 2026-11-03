# Deployment

## Environments
Changes flow from staging to production. Staging uses anonymised copies of production data that
are refreshed every Monday.

## Releases
The main branch deploys to staging on every merge. Production deploys happen Tuesday to Thursday
between 10:00 and 16:00 UTC; there are no Friday deploys.

## Health checks
Every service exposes `/health` (process is up) and `/ready` (dependencies are reachable). The
load balancer removes an instance after three failed readiness checks in a row.

## Rollbacks
Every release can be rolled back with one command: `orderly deploy rollback <service>`. Database
migrations must therefore stay compatible with the previous release.

## Feature flags
Risky features ship behind a flag in the flag service and are enabled for 5 percent of traffic
before a full rollout.
