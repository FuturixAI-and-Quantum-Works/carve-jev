# Security policy

## Supported versions

Security fixes are applied to the latest release and the default branch.

## Reporting

Use GitHub's private vulnerability reporting feature. If it is unavailable,
contact the repository owner privately. Do not open a public issue containing
an exploit, secret, private user data, or unpatched vulnerability.

Include the affected version, impact, reproduction steps, and suggested
mitigation. Maintainers will acknowledge a report when possible and coordinate
disclosure after a fix.

## Deployment boundary

CARVE's development server does not authenticate bearer tokens and does not
provide TLS, rate limits, or request-size limits. Bind it to a trusted
interface and use a hardened gateway before network exposure. Treat submitted
state and media as potentially sensitive. Do not log them without an explicit
retention and access policy.
