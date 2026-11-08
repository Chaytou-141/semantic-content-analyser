# Security policy

This is a limited portfolio/demo application, not a security-certified service.
Security fixes target the current maintained branch; older commits and historical
verification artifacts are not separately supported releases.

## Report privately

Use the repository's **Security > Advisories > Report a vulnerability** option when
private vulnerability reporting is enabled:
https://github.com/Chaytou-141/semantic-content-analyser/security/advisories/new

Do not put passwords, tokens, personal data, private article text or exploit details
in public issues or pull requests. If the private reporting option is unavailable,
open an issue containing only a request for a private reporting channel; wait for
maintainer instructions before sharing sensitive details. No private email or other
personal contact information is published here.

Include the affected commit/version, the feature involved, expected versus actual
behaviour, impact and minimal reproduction using synthetic data. Redact credentials
and provide logs privately only when necessary. Never upload a production database.

Use a local disposable environment for testing. Do not perform disruptive tests,
resource-exhaustion attacks, scans of other visitors' data or attempts against AWS
metadata/private networks on the live demo. The public demo is not blanket permission
for penetration testing. Coordinate any live testing privately with the maintainer.

Reports are handled on a best-effort basis; no guaranteed response time or bounty is
promised. Retain known advisory findings until remediation or an explicit documented
risk decision. Do not interpret a passing test suite as a guarantee of safety.

As part of publication, the maintainer must enable and verify GitHub private
vulnerability reporting when the repository supports it. This file alone does not
activate that GitHub setting.
