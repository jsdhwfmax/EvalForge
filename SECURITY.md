# Security policy

## Reporting a vulnerability

Please do not open a public issue for vulnerabilities that expose credentials, private datasets, or a deployed EvalForge instance. Use GitHub's private vulnerability reporting for this repository. Include affected version, reproduction, impact, and any suggested mitigation.

The maintainer targets an acknowledgment within three business days and an initial severity assessment within seven. Target remediation windows are 14 days for critical issues and 30 days for high-severity issues, subject to coordinated disclosure and the availability of a safe fix. These are response targets, not a warranty.

Security fixes are made for the latest released minor version during the pre-1.0 period. Reporters will be credited unless they request anonymity.

## Deployment warning

Production deployments require `EVALFORGE_ENVIRONMENT=production` and the same securely
generated `EVALFORGE_ACCESS_KEY` on the API and dashboard. Data routes require Bearer
authentication; the dashboard requires sign-in before it fetches or displays data. Health
checks and API documentation remain public. Local development without an access key remains
unauthenticated and should bind only to loopback.

The shared key grants full maintainer access, including provider configuration and experiment
execution. It does not provide individual user identities or tenant isolation. Use an
authenticated gateway or identity-aware proxy when those are needed, terminate public traffic
with HTTPS, and share maintainer access only with trusted operators. A maintainer can configure
provider destinations and the environment variable used for provider credentials. Store keys
only in environment-secret systems; rotate the shared key on both services and restart them to
invalidate existing dashboard sessions. See [deployment instructions](docs/DEPLOYMENT.md).

The adversarial evaluation suite measures model behavior; it is not itself an application security boundary.
