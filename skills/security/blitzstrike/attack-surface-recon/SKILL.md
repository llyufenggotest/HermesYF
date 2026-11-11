---
name: attack-surface-recon
description: "Use when you need to know what's actually exposed for a…"
version: 0.1.0
author: "shinthink (Blitz Strike), Hermes Agent"
license: MIT
tier: archive
---

# Attack surface recon

Passive-first, then active. The goal is a target list and a tech-stack map, not exploitation.

## Prerequisites

- `subfinder`, `dnsx`, `httpx`, `katana`, `naabu` (all from ProjectDiscovery — `TOOLS.md` has install commands)

## Workflow

1. **Subdomain enumeration** (passive, safe against anything):
   ```bash
   subfinder -d example.com -all -silent -o findings/subdomains.txt
   ```

2. **Resolve and dedupe** to confirm which subdomains are actually live DNS records:
   ```bash
   dnsx -l findings/subdomains.txt -silent -o findings/resolved.txt
   ```

3. **Probe for live HTTP(S) services** and fingerprint tech stack, status codes, titles:
   ```bash
   httpx -l findings/resolved.txt -silent -title -tech-detect -status-code -o findings/live-hosts.txt
   ```

   ```bash
   naabu -l findings/resolved.txt -top-ports 1000 -silent -o findings/open-ports.txt
   ```

5. **Crawl for endpoints** on each live host to build a URL corpus for later injection/fuzzing skills:
   ```bash
   katana -u findings/live-hosts.txt -silent -o findings/endpoints.txt -jc -kf all
   ```

6. **Cross-reference tech-detect output** (from httpx) against known CVEs for that stack/version — feed into `dependency-audit` or `dast-active-scan` for the matching nuclei templates.

## Output

`findings/` should end this skill with: `subdomains.txt`, `resolved.txt`, `live-hosts.txt` (with tech stack), `open-ports.txt`, `endpoints.txt`. These feed directly into `web-app-pentest`, `api-security-test`, `network-service-scan`, and `dast-active-scan`.

## Notes

- Everything through step 3 is passive/near-passive (public DNS + certificate transparency + normal HTTP requests) and low-risk against your own infrastructure. Step 4 (port scanning) and step 5 (crawling) generate real traffic — keep scan rate sane (`naabu` and `katana` both support `-rate`/`-c` flags) and don't run them against anything you don't control.
- An unexpectedly large `live-hosts.txt` (forgotten staging environments, old marketing subdomains, dev tooling like Jenkins/Grafana left exposed) is itself a finding — flag it even if nothing else is wrong with it.
