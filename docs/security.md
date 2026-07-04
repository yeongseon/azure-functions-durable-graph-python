# Security

This document outlines the security policies, reporting processes, and scanning tools used in the azure-functions-durable-graph library. We take the security of this project seriously and appreciate responsible disclosure.

## Reporting Vulnerabilities

If you discover a security vulnerability in this project, please report it privately. Avoid public disclosure through issues or pull requests until a fix is available and a coordinated release has been prepared.

### Preferred: GitHub Security Advisory

The most secure way to report a vulnerability is through a GitHub Security Advisory. This allows for private collaboration between the reporter and maintainers.

1. Navigate to the [Security Advisories page](https://github.com/yeongseon/azure-functions-durable-graph-python/security/advisories/new).
2. Click "Report a vulnerability" or "New advisory".
3. Provide the details of the issue in the private advisory form.

### Alternative: Email

If you prefer to use email, you can reach the maintainer at: yeongseon.choe@gmail.com.

### What to Include in Your Report

To help us triage and address the issue efficiently, please include:

- A clear and detailed description of the vulnerability.
- Step-by-step instructions to reproduce the issue.
- An assessment of the potential impact (e.g., data leakage, remote execution).
- Suggested mitigation steps or a potential fix, if available.

### Response Timeline

We aim to respond to all security reports within the following timeframes:

- Initial response: Within 48 hours of receiving the report.
- Status update: Within 7 days of the initial response, detailing progress or required information.

## Supported Versions

Security support is provided for the current active release. Older versions are not actively maintained for security patches.

| Version | Supported |
| --- | --- |
| Latest release | Yes |
| Older releases | No |

## Security Scanning

We use automated tools to ensure the codebase remains secure and follows best practices.

### Bandit: Static Analysis Security Scanner

Bandit is used for static analysis security scanning of Python code. It is configured to scan the source code while skipping test files to minimize false positives.

You can run a security scan locally using the following commands:

```bash
# Using make
make security

# Using hatch
hatch run security
```

The underlying command executed is `python -m bandit -r src`.

### CI/CD Integration

Security scans are integrated into our continuous integration pipeline. Every push and pull request triggers the `security.yml` workflow via GitHub Actions, ensuring that no known security regressions are introduced into the main branch.

## Security Scope

Understanding the boundaries of this library is essential for building secure Azure Functions.

### Within Scope

- **Orchestrator Determinism**: The runtime enforces that all user logic runs in activities, preventing accidental non-deterministic behavior in the orchestrator.
- **State Validation**: Pydantic v2 manages state validation at every node transition, ensuring data integrity throughout graph execution.

### Out of Scope

- **Authentication and Authorization**: This library does not handle user identity or permission checks. Use the built-in Azure Functions authentication levels or custom middleware.
- **LLM Security**: Prompt injection, output validation, and LLM-specific security are the responsibility of the node handler implementations.
- **Rate Limiting**: Protection against denial-of-service (DoS) attacks via rate limiting is managed at the Azure API Management or Azure Functions platform level.
- **Encryption**: Data-at-rest and data-in-transit encryption are handled by the Azure platform and underlying Python runtime.

Azure Functions runtime security and platform-level infrastructure are managed by the Azure platform and are outside the control of this library.

## Security Best Practices for Users

When using this library, follow these practices to enhance your application's security:

1. **Validate All Inputs**: Use strict Pydantic models for state definitions with field constraints (`min_length`, `max_length`, `ge`, `le`, `pattern`).
2. **Sanitize LLM Outputs**: If node handlers call LLMs, validate and sanitize responses before merging into state.
3. **Use Authentication**: Set `auth_level=func.AuthLevel.FUNCTION` or higher for production deployments.
4. **Keep Dependencies Updated**: Regularly update `pydantic`, `azure-functions`, and `azure-functions-durable` to benefit from the latest security patches.

## Dependency Security

We maintain a minimal dependency surface to reduce the attack vector.

- **Core Dependencies**: `azure-functions`, `azure-functions-durable`, `pydantic`, `typing-extensions`.
- **Dependabot**: Automated dependency updates are enabled via Dependabot to ensure that security vulnerabilities in upstream packages are addressed quickly.
- **Regular Audits**: We perform regular dependency audits to identify and mitigate risks from third-party code.
