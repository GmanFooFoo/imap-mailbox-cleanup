---
name: mailbox-cleanup
description: Discover and clean up the IONOS IMAP mailbox german@rauhut.com via the `mailbox-cleanup` CLI. Use when the user wants to triage, scan, delete, archive, or unsubscribe from messages in their mail account. Always shows dry-run preview before any destructive operation.
---

# mailbox-cleanup

Conversational orchestrator over the `mailbox-cleanup` CLI. Wraps discovery → preview → apply loops with safety checks.

## Account

Single IONOS mailbox: `german@rauhut.com`. The CLI reads credentials from macOS Keychain.

## Required CLI version

Schema version 1. The CLI emits `"schema_version": 1` in every JSON response — if it doesn't match, abort and tell the user to update the CLI.

## Setup check (run first, every session)

Before any operation, verify the CLI is reachable and authenticated:

```bash
mailbox-cleanup auth test --email german@rauhut.com --json
```

- Exit 0 with `"ok": true`: continue.
- Exit 3 (`auth_missing`): tell the user to run `mailbox-cleanup auth set --email german@rauhut.com --server imap.ionos.de` in their terminal. Do not proceed.
- Exit 2 (connection): show the message; do not retry blindly.

## Standard flow

1. Run `mailbox-cleanup scan --email german@rauhut.com --json`.
2. Validate `schema_version == 1`. Otherwise abort.
3. Render a German Markdown summary:

   ```
   Mailbox: <total_messages> Nachrichten, <size_total_mb> MB

   Kategorien:
     1. Newsletter: <count> (Top-Sender: ...)
     2. Automatisierte Notifications: <count>
     3. Bounces / Auto-Replies: <count>
     4. Große Anhänge (>10 MB): <count> Nachrichten, <size_mb> MB
     5. Alte Nachrichten: <older_than_12m> älter als 12 Monate
     6. Duplikate: <count>

   Empfehlungen:
     [1] <recommendations[0]>
     [2] <recommendations[1]>
     ...
   ```

4. Ask: **"Welche Kategorie / Empfehlung willst du angehen?"**
5. When the user picks an operation:
   - Always run the CLI **without `--apply`** first (dry-run)
   - Render the preview: count + first 5 sample messages
   - Ask: **"Apply?"**
   - Only on explicit confirmation, run again with `--apply`
6. After `--apply`, show the result count and tell the user the audit log is at `~/.mailbox-cleanup/audit.log`.
7. Loop back to step 4 for the next category.

## Subcommand cheat sheet

| User intent | Command |
|-------------|---------|
| "Scan" / "Was ist drin?" | `mailbox-cleanup scan --email german@rauhut.com --json` |
| "Wer schickt am meisten?" | `mailbox-cleanup senders --email german@rauhut.com --top 20 --json` |
| "Lösch alles von X" | `mailbox-cleanup delete --email german@rauhut.com --sender X --json` (then `--apply`) |
| "Alles älter als 1 Jahr archivieren" | `mailbox-cleanup archive --email german@rauhut.com --older-than 12m --json` |
| "Vom Newsletter X abmelden" | `mailbox-cleanup unsubscribe --email german@rauhut.com --sender X --json` |
| "Bounces wegräumen" | `mailbox-cleanup bounces --email german@rauhut.com --json` |
| "Duplikate finden" | `mailbox-cleanup dedupe --email german@rauhut.com --json` |
| "Große Anhänge zeigen" | `mailbox-cleanup attachments --email german@rauhut.com --size-gt 10mb --json` |

## Exit codes

| Code | Meaning | What to do |
|------|---------|------------|
| 0 | Success | Continue |
| 2 | Connection error | Show stderr, do not retry blindly |
| 3 | Auth missing | Tell user to run `auth set` |
| 4 | Bad arguments | Show stderr; you used the CLI wrong, fix the call |
| 5 | Partial failure | Show audit log path, summarize successes/failures |

## Hard rules

1. **Never call any subcommand with `--apply` without showing a dry-run preview first and getting explicit "ja" / "yes" / "apply" from the user.**
2. **Never invent UID lists or counts.** Always use the JSON returned by the CLI.
3. **Never edit the audit log.** It is append-only forensics.
4. **All destructive operations move to Trash.** v1 has no hard-delete; if the user asks "wirklich löschen", explain that v1 only soft-deletes and Trash is purged by IONOS retention.
