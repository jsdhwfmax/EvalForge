# Security policy

## Reporting a vulnerability

Please do not open a public issue for vulnerabilities that expose credentials, private datasets, or a deployed EvalForge instance. Use GitHub's private vulnerability reporting for this repository. Include affected version, reproduction, impact, and any suggested mitigation.

The maintainer targets an acknowledgment within three business days and an initial severity assessment within seven. Target remediation windows are 14 days for critical issues and 30 days for high-severity issues, subject to coordinated disclosure and the availability of a safe fix. These are response targets, not a warranty.

Security fixes are made for the latest released minor version during the pre-1.0 period. Reporters will be credited unless they request anonymity.

## Deployment warning

The MVP does not implement user authentication or tenant isolation. Do not expose it to the public internet with confidential datasets unless it is protected by an authenticated API gateway or identity-aware proxy. Store provider keys only in environment-secret systems.

The adversarial evaluation suite measures model behavior; it is not itself an application security boundary.
