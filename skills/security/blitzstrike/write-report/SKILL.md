---
name: write-report
description: "Use when finalizing confirmed findings into a submission…"
version: 0.1.0
author: "shinthink (Blitz Strike), Hermes Agent"
license: MIT
tier: archive
---

# Write the report

Turn confirmed findings into a submission-ready deliverable. A triager should
not be able to tell an agent wrote it.

## Structure per finding

1. **Title + summary** — one line, precise, no clickbait.
2. **Root cause** — the exact code path (source → sink), not a generic description.
3. **Reproduction steps** — exact request(s) + the marker/control proof from
   `verify-finding`.
4. **Impact** — what an attacker actually gains (data, RCE, account takeover).
5. **CVSS** — `cvss_score` with the correct vector string; do not inflate.
6. **Remediation** — concrete, implementable, framework-appropriate.

## Tools

- `generate_report` — deterministic markdown/JSON report from the findings.
- `cvss_score` — deterministic CVSS v3.1 vector.
- `redact` — strip passwords/keys/tokens/cookies before any output.
- `finding_attach_evidence` — link the redacted, SHA-256-tagged evidence.

## Two audiences — pick before writing

**Remediation brief** ("提交给开发/运维团队"): risks, impact scope, fixes with
concrete config/code, acceptance criteria. No attack chain, no exploit step
list, no harvested-data counts. Every P0 carries paste-ready nginx `location`,
the `getenv()` / env-var refactor, an `iptables` block, or the `sshd_config`
lines — plus a "retest" section pairing each fix with the exact curl command
and expected status code, so the dev can check it off as a ticket.

**Pentest report** ("真实一点 / 攻击链写清楚"): phase-by-phase chain (fingerprint →
source leak → hardcoded credential → object-level authz bypass → data
extraction → live verification), each phase with the exact URL and a response
excerpt, plus the sample records actually obtained (id / plan / volume / uuid /
token / fetch result). Add a timeline section — it shows the test advanced in
stages rather than one brute-force pass.

Never blend the two into one document; ask which one is wanted if unclear.

## Secrets in reports — two levels

- **The target's own infrastructure secrets** (bridge API token, DB password,
  encryption hash): describe them ("a 9-digit numeric token"), do not print the
  value. The owner already knows it.
- **Credentials harvested as proof** (victim `uuid`, `subscribe_token`, node
  password): the pentest report SHOULD include them verbatim — that is the
  evidence, and redacting it leaves nothing to verify. Redact only when the
  report goes to a third party (bug bounty / SRC / public writeup).
- Live verification beats assertion: "subscription → egress 189.24.x.x (US/LA),
  switching node → egress changed to …" outweighs "subscription works".

## Rules

- Only CONFIRMED findings (passed `adversarial-review`) go in the report.
- No false-positive spam, no "low-hanging fruit" filler.
- Group by root cause; a report full of duplicates reads as noise.
- Deliver Markdown plus a print-styled HTML (Ctrl+P → PDF); give `pre`/`table`
  `page-break-inside: avoid` so code blocks and tables don't split across pages.

