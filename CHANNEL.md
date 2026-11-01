# MAIL CHANNEL — READ FIRST IN EVERY NEW SESSION

> **TL;DR: run `python3 scripts/atomicmail_recover.py` BEFORE any email work.
> Do NOT create a new mailbox unless that script fails verification with
> HTTP 401/403.** Three accounts were already burned to sandbox wipes
> (see history below). Recovering takes 5 seconds; re-registering burns
> reputation, rate caps, and orphans skorry's reply address.

## Current channel (update after any change)

| Field | Value |
|---|---|
| Address | `asha.jobtoolkit3@atomicmail.ai` |
| Recipient | `skorry@atomicmail.io` (owner's inbox — always BCC-less direct) |
| Registered | 2026-10-14 (Task 18-b), PoW signup |
| Rate caps | 20 msgs/h, 100 msgs/d |
| Credentials | `~/.atomicmail/credentials.json` (apiKey + JMAP URLs) |
| Send pattern | `scripts/atomicmail_send_task18.py` = ops-json + `npx -y --package=@atomicmail/agent-skill atomicmail jmap_request` |
| Escrowed | commit containing `scripts/atomicmail_escrow.json.enc` |

## Recovery decision tree

```
python3 scripts/atomicmail_recover.py
├─ exit 0, "CHANNEL READY"          → done. Send mail normally.
├─ network error / timeout          → re-run --verify-only in a minute.
└─ HTTP 401/403 (key revoked)       → LAST RESORT (below). Never skip to this.
```

## Escrow tiers (written by `scripts/make_escrow.py`)

| Tier | Location | Survives |
|---|---|---|
| 1 | `scripts/atomicmail_escrow.json.enc` — AES-256 ciphertext, **git-committed** | everything: wipes, working-tree resets, and it rides inside every backup bundle |
| 2 | `state/atomicmail_escrow.json` (gitignored, 0600) | most wipes, not guaranteed |
| 3 | `/home/z/.config/atomicmail/escrow.json` (0600) | repo wipes, not `~` wipes |

Recovery self-heals weaker tiers from the strongest one found. After ANY
re-registration or login: **re-run `make_escrow.py`** so tier 1 is refreshed
and commit it.

**Key-rotation note (verified empirically 2026-10-14):** the server may return
a NEW apiKey on every login, but old keys stay valid. Consequence: the escrow
can never be stranded by a rotation, and recovery auto-adopts/re-escrows the
newest key whenever it runs a full (non-`--verify-only`) pass.

### Why the passphrase is committed (security decision, 2026-10-14)

`scripts/escrow_key.py` holds the AES passphrase **in git, on purpose**. The
only store guaranteed to survive every wipe is git history, and an escrow
whose key is nowhere durable is an escrow that fails exactly when needed —
that failure mode is what burned accounts #1 and #2. Accepted trade-off: a
bundle mirror reader could reconstruct the key, but it guards only a
throwaway relay inbox (no PII, no access to skorry's account). **Rotation
recipe** is in the header of `scripts/escrow_key.py`.

## Last-resort re-registration (only on 401/403)

1. `python3 scripts/mailtm.py` — fresh verification inbox (mail.tm)
2. `npx -y --package=@atomicmail/agent-skill atomicmail register --username <newname> --watch on-demand` (PoW; caps 20/h 100/d; watch value is the project-documented choice)
3. `python3 scripts/make_escrow.py --address <new>@atomicmail.ai --note "re-registered <date>: <reason>"`
4. `git add scripts/atomicmail_escrow.json.enc scripts/escrow_key.py && git commit`
5. **Email skorry the new address from the old account if still possible, else note it in the worklog** — old replies bounce otherwise
6. Update the channel block above + worklog

## Burned-account history (why this file exists)

| # | Address | Born | Died | Cause |
|---|---|---|---|---|
| 1 | `asha.jobtoolkit@atomicmail.ai` | Task 12 era | 2026-10-14 ~08:24 | wipe destroyed `~/.atomicmail`; no escrow existed |
| 2 | `asha.jobtoolkit2@atomicmail.ai` | Task 16 | by Task 18 | key escrowed only in a **gitignored** handover doc → wiped |
| 3 | `asha.jobtoolkit3@atomicmail.ai` | Task 18-b | — | key lived only in `~/.atomicmail` until Task 19 escrowed it properly |

## Related

- `BACKUPS.md` — repo bundle mirrors (v6/v7) + upload recipes
- `worklog.md` — append-only cross-session task log
- `scripts/atomicmail_recover.py --help` — recovery flags

## GitHub (account: shalosi00) — since Task 23, 2026-10-26

- PAT lives in `state/github_token` (0600, **gitignored on purpose** — unlike the
  atomicmail escrow, this key can push to PUBLIC repos, so it must never ride in
  bundles/mirrors). If state is wiped: ask user for a fresh key in-session.
- Use: `curl -H "Authorization: token $(cat state/github_token)" https://api.github.com/...`
- Key repos: `proxyfetch` (generic proxy scraper CLI, v0.3.1+seed feature),
  `erlangen-jobs` (public job pipeline w/ map + geo, strict proxy-only networking).
- Learned 2026-10-26: kimeta TLS-fingerprints clients — proxyfetch's aiohttp
  engine gets 503 through proxies where the pipeline's requests stack passes.
  For kimeta use `pipeline/sources/kimeta.py`; for everything else proxyfetch.

- **NEW AGENT?** Start with `AI_HANDOVER_PROXY_BROWSER.md` (Task 24c) — full verified instructions for the proxied fetching stack incl. the GitHub PAT (user-authorized to include there).
