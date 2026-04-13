# Security Policy

## Supported Versions

Security fixes are expected to land in the latest released version of this
integration and on the current `main` branch.

Older versions may not receive fixes.

## Reporting a Vulnerability

Please do not open a public GitHub issue for vulnerabilities that could expose:

- MyEdenred credentials such as `Username` or `Password`
- authenticated session tokens
- personal card numbers
- unexpected redirects or data leaks from the MyEdenred flow

Prefer GitHub's private vulnerability reporting for this repository if it is
available. If private reporting is not available, contact the maintainer
privately through GitHub instead of posting the details publicly.

When reporting a vulnerability:

- describe the impact and the conditions required to reproduce it
- include the integration version or commit SHA
- include Home Assistant and Python versions if relevant
- redact credentials, cookies, session identifiers, and private account data

## Security Notes

This integration depends on a third-party website and login flow controlled by
Edenred Portugal. As of `2026-04-13`, the project primarily targets the JSON
API pattern previously used by `www.myedenred.pt`, with an HTML balance parser
kept as a fallback for the `.card-balance.autoNumeric` dashboard element.

Because of that upstream dependency, the project treats the following as
security-sensitive areas:

- credential handling in the Home Assistant config flow
- auth failures and token refresh handling
- card identifiers and masked number presentation
- fallback HTML parsing changes that could accidentally expose private data
