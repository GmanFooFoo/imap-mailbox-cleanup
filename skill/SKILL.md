---
name: mailbox-cleanup
description: Discover and clean up an IONOS IMAP mailbox via the `mailbox-cleanup` CLI. Use when the user wants to triage, scan, delete, archive, or unsubscribe from messages in their mail account. Always shows dry-run preview before any destructive operation.
---

# mailbox-cleanup

Conversational orchestrator over the `mailbox-cleanup` CLI. Wraps discovery → preview → apply loops with safety checks.

## Account email

The CLI is currently designed for a single mailbox (multi-account support is v2). Get the user's IONOS email address **on first invocation in a session**, then reuse it consistently in all CLI calls.

How to get it:
1. If the environment variable `MAILBOX_CLEANUP_EMAIL` is set, use that.
2. Otherwise, ask the user: "Welche IONOS-Mailbox soll ich aufräumen? (z.B. `name@example.com`)"
3. Once you have it, store it in your working memory for the session and substitute it into every `--email` flag below.

In the rest of this document, `<EMAIL>` is the placeholder — replace it with the user's actual email when constructing CLI calls.

## Required CLI version

Schema version 1. The CLI emits `"schema_version": 1` in every JSON response — if it doesn't match, abort and tell the user to update the CLI.

## Setup check (run first, every session)

Before any operation, verify the CLI is reachable and authenticated:

```bash
mailbox-cleanup auth test --email <EMAIL> --json
```

- Exit 0 with `"ok": true`: continue.
- Exit 3 (`auth_missing`): tell the user to run `mailbox-cleanup auth set --email <EMAIL> --server imap.ionos.de` in their terminal (Terminal.app / iTerm — `getpass` requires a TTY). Do not proceed.
- Exit 2 (connection): show the message; do not retry blindly.

## Standard flow

1. Run `mailbox-cleanup scan --email <EMAIL> --json`.
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

Replace `<EMAIL>` with the user's email when issuing each command.

| User intent | Command |
|-------------|---------|
| "Scan" / "Was ist drin?" | `mailbox-cleanup scan --email <EMAIL> --json` |
| "Wer schickt am meisten?" | `mailbox-cleanup senders --email <EMAIL> --top 20 --json` |
| "Lösch alles von X" | `mailbox-cleanup delete --email <EMAIL> --sender X --json` (then `--apply`) |
| "Alles älter als 1 Jahr archivieren" | `mailbox-cleanup archive --email <EMAIL> --older-than 12m --json` |
| "Vom Newsletter X abmelden" | `mailbox-cleanup unsubscribe --email <EMAIL> --sender X --json` |
| "Bounces wegräumen" | `mailbox-cleanup bounces --email <EMAIL> --json` |
| "Duplikate finden" | `mailbox-cleanup dedupe --email <EMAIL> --json` |
| "Große Anhänge zeigen" | `mailbox-cleanup attachments --email <EMAIL> --size-gt 10mb --json` |

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
