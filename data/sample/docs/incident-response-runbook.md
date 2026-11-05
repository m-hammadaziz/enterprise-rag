# Incident Response Runbook

## Severity levels

- SEV1: complete outage or data loss affecting customers. Response within 15 minutes, all hands, status page update within 30 minutes.
- SEV2: major feature degraded for many customers. Response within 30 minutes.
- SEV3: minor degradation or a single customer affected. Response within 4 business hours.

## On-call rotation

The primary on-call rotation is weekly and hands over every Monday at 10:00 UTC. Each team keeps a primary and a secondary on-call engineer. On-call engineers receive a stipend of 300 USD per week of on-call duty.

Pages are sent through PagerTree. If the primary does not acknowledge a page within 10 minutes, it escalates automatically to the secondary.

## Running an incident

For every SEV1 and SEV2 the on-call engineer opens a dedicated Slack channel named #inc-<date>-<short-name> and assigns an Incident Commander. The Incident Commander owns communication; engineers focus on mitigation.

Customer-facing updates are posted on status.corvane.example at least every 30 minutes during a SEV1.

## Postmortems

A blameless postmortem is required for every SEV1 and SEV2 and must be published within 5 business days of the incident. Action items are tracked in the RELIABILITY Jira project and must have an owner and a due date.

## Rollback first

When a deploy is the suspected cause, roll back first and investigate afterwards. Rollbacks do not require change approval.
