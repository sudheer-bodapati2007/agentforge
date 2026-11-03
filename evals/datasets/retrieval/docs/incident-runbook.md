# Incident runbook

## Severity levels
SEV1: checkout or payments are down for all customers. Page the on-call engineer and the
engineering manager immediately. SEV2: a major feature is degraded. SEV3: a minor bug with a
workaround; handle it during working hours.

## On-call
The on-call engineer acknowledges a page within 5 minutes and posts updates in the #incidents
channel every 30 minutes until the incident is resolved.

## After an incident
Every SEV1 and SEV2 gets a blameless postmortem within five working days, with action items that
have owners and due dates.
