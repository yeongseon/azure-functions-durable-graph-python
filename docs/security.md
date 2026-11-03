# Security

> **Retired and unsupported as of 2026-10-02.** No maintenance, fixes or security
> updates will be provided. `yeongseon` never published an official PyPI release of
> `azure-functions-durable-graph`. Do not treat a same-named PyPI project as official.
> Tags and GitHub releases are historical source snapshots only.

## Supported versions and response commitments

**There are no supported versions.** No snapshot or GitHub release receives security
fixes. Former 48-hour response and seven-day update targets no longer apply. There is
no commitment to triage, remediate, publish an advisory or coordinate a release.

## Voluntary private contact

You may share a historical-source finding privately with yeongseon.choe@gmail.com
or through the
[GitHub private reporting form](https://github.com/yeongseon/azure-functions-durable-graph-python/security/advisories/new)
if available. Include reproduction steps, source commit and impact, without secrets
or personal data. This is a voluntary information channel, not a supported-service
or response-time promise. Do not wait for a promised fix: none is planned.

The repository's
[SECURITY.md](https://github.com/yeongseon/azure-functions-durable-graph-python/blob/main/SECURITY.md)
is the security policy.

## Historical security model

The retained runtime placed user handlers in Durable Functions activities for
orchestrator determinism and used Pydantic v2 for state validation. It did not
provide application authentication, authorization, rate limiting, encryption or
LLM prompt-injection defenses. These descriptions are historical design context,
not a guarantee that the unsupported source is secure for deployment.

`make security` runs the retained local Bandit scan. A passing scan is not proof of
security or a maintenance commitment. There are no regular dependency-audit or
automated-update commitments. Release, publishing, Azure E2E and dependency auto-merge
workflows remain disabled; documentation cleanup does not authorize enabling them.
Revival requires an explicit maintainer decision and updated, re-audited dependencies
and Actions before re-enabling workflows, as recorded in
[PR #209](https://github.com/yeongseon/azure-functions-durable-graph-python/pull/209#issuecomment-5944447065).
