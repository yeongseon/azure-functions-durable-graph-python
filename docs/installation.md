# Installation

> **Retired and unsupported as of 2026-10-02.** This project receives no maintenance,
> fixes or security updates. `yeongseon` never published an official PyPI release of
> `azure-functions-durable-graph`. Do not treat a same-named PyPI project as official.
> Existing history, tags and GitHub releases are historical source snapshots only.

## Installation and upgrades

There is no official maintainer PyPI package to install or upgrade, no supported
release, and no recommended production installation. Former PyPI installation and
“latest published version” upgrade instructions did not establish an official release.
No successor package or migration compatibility is asserted here.

## Historical compatibility

The retained `pyproject.toml` declares Python `>=3.10,<3.15`, Pydantic v2,
`azure-functions>=1.17,<2.0.0` and `azure-functions-durable>=1.2.0,<3`.
These describe the source snapshot, not a currently supported environment. The
runtime targeted the Azure Functions Python v2 programming model and a v4 host.

## Local source inspection and documentation validation

For historical inspection or a documentation correction only:

```bash
git clone https://github.com/yeongseon/azure-functions-durable-graph-python.git
cd azure-functions-durable-graph-python
make install
make check-all
make docs
```

This uses the repository source, not an official PyPI distribution. Local dependency
installation and builds do not make the snapshot supported or safe for deployment.
Retained examples and API descriptions are historical; inspect them without exposing
an unsupported app to production traffic.

The retirement rule in
[CONTRIBUTING.md](https://github.com/yeongseon/azure-functions-durable-graph-python/blob/main/CONTRIBUTING.md#retirement-rule)
overrides linked development and release instructions. Documentation cleanup does
not authorize feature work, dependency maintenance, release recovery, credential
renewal, publishing or re-enabling automation. Revival requires an explicit maintainer
decision and updated, re-audited dependencies and Actions before workflows are
re-enabled, as recorded in
[PR #209](https://github.com/yeongseon/azure-functions-durable-graph-python/pull/209#issuecomment-5944447065).
