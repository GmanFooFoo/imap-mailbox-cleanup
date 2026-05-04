# mailbox-cleanup

Hybrid CLI + Claude Code Skill for triaging and cleaning up an IONOS IMAP mailbox. Dry-run by default, audit-logged, soft-delete-only.

[![CI](https://github.com/GmanFooFoo/mailbox-cleanup/actions/workflows/ci.yml/badge.svg)](https://github.com/GmanFooFoo/mailbox-cleanup/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/license-private-lightgrey.svg)](#license)

---

## What it does

Battle-tested in one production session: 7.982 → 690 messages (-91%) on a real IONOS mailbox.

Two pieces:

1. **CLI** (Python, [`click`](https://click.palletsprojects.com), [`imap-tools`](https://github.com/ikvk/imap_tools)) — atomic subcommands with JSON output. Stateless. Testable.
2. **Claude Code Skill** — conversational orchestrator that wraps the CLI in a discovery → preview → apply loop. Asks before every destructive action.

The CLI is useful on its own. The Skill turns it into a guided triage workflow.

## Why hybrid

- **Pure CLI** would force you to memorize subcommands and read JSON.
- **Pure Skill** would push IMAP logic into Markdown / tool calls — fragile, slow, untestable.
- **Hybrid** keeps the engine testable (`pytest` against a real IMAP server in Docker) and the UX conversational.

## Architecture

```
Claude Code Session
  ↓ /mailbox-cleanup or natural request
Claude Skill (Markdown, orchestrator)
  ↓ subprocess + JSON
CLI: mailbox-cleanup <subcommand> [--apply | --json]
  ↓ imap-tools
IONOS IMAP
```

## Safety model

| Layer | Mechanism |
|-------|-----------|
| **Default** | Every destructive subcommand is dry-run. `--apply` is required to actually do anything. |
| **Soft-delete** | `delete` moves to `Papierkorb` / `Trash` (resolved via RFC 6154 SPECIAL-USE flag with literal fallbacks). No `EXPUNGE` in v1. |
| **Skill flow** | Always shows a preview from a dry-run before re-running with `--apply`. Asks for explicit confirmation. |
| **Audit log** | Every `--apply` action appends one JSON-line to `~/.mailbox-cleanup/audit.log` with timestamp, args, folder, affected UIDs, and result. |
| **Credentials** | macOS Keychain via [`keyring`](https://github.com/jaraco/keyring). No `.env`, no plaintext. |
| **Final step** | True deletion is manual — empty `Papierkorb` in IONOS Webmail. |

## Install

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) (`brew install uv`).

```bash
git clone https://github.com/GmanFooFoo/mailbox-cleanup.git
cd mailbox-cleanup
uv tool install --editable .
```

This puts `mailbox-cleanup` on your `PATH` (typically `~/.local/bin/mailbox-cleanup`).

### One-time auth

In a real terminal (Terminal.app / iTerm — `getpass` requires a TTY):

```bash
mailbox-cleanup auth set --email you@example.com --server imap.ionos.de
```

Verify:

```bash
mailbox-cleanup auth test --email you@example.com --json
```

### Optional: install the Claude Code Skill

```bash
mkdir -p ~/.claude/skills/mailbox-cleanup
cp skill/SKILL.md ~/.claude/skills/mailbox-cleanup/
```

Claude Code auto-discovers skills under `~/.claude/skills/`. Invoke via `/mailbox-cleanup` in any session.

## Usage

### From Claude Code

```
/mailbox-cleanup
```

The Skill runs `auth test`, then `scan`, presents a German-language category summary, and prompts for action per category. Always shows a dry-run preview before any `--apply`.

### Standalone CLI

```bash
# Discovery
mailbox-cleanup scan --email you@example.com --json
mailbox-cleanup senders --email you@example.com --top 50

# Dry-run delete (preview only)
mailbox-cleanup delete --email you@example.com --sender "newsletter@x.com"

# Apply
mailbox-cleanup delete --email you@example.com --sender "newsletter@x.com" --apply

# Combine filters (AND)
mailbox-cleanup delete \
  --email you@example.com \
  --sender "noreply@github.com" \
  --older-than 6m \
  --apply

# Move (e.g. invoices to a tax folder)
mailbox-cleanup move \
  --email you@example.com \
  --sender "noreply@ionos.de" \
  --to "STEUER Rechnungen Finanzamt" \
  --apply

# Bulk archive
mailbox-cleanup archive --email you@example.com --older-than 12m --apply

# Unsubscribe (RFC 2369 / RFC 8058 one-click)
mailbox-cleanup unsubscribe --email you@example.com --sender "newsletter@x.com" --apply

# Dedupe by Message-ID (keeps oldest)
mailbox-cleanup dedupe --email you@example.com --apply

# Find bounce / auto-reply
mailbox-cleanup bounces --email you@example.com --apply

# List large attachments (strip = v2)
mailbox-cleanup attachments --email you@example.com --size-gt 10mb
```

## Subcommands

| Subcommand | Purpose | Required args | Dry-run by default |
|------------|---------|---------------|---------------------|
| `auth set` | Write IONOS credentials to macOS Keychain | — (interactive) | n/a |
| `auth test` | Connect, list folders, disconnect | — | n/a |
| `auth delete` | Remove credentials from Keychain | `--email` | n/a |
| `scan` | Discovery — classify INBOX, return JSON report | `--folder=INBOX` (default) | n/a (read-only) |
| `senders` | List top-N senders by count | `--top=50` | n/a (read-only) |
| `delete` | Soft-delete (move to Trash) by filter | one of `--sender=` / `--subject-contains=` / `--older-than=` | yes |
| `move` | Move by filter to target folder | `--from-filter=...`, `--to=Folder` | yes |
| `archive` | Bulk-move messages older than N → `Archive/YYYY` | `--older-than=12m` | yes |
| `unsubscribe` | Parse `List-Unsubscribe` header, execute (HTTPS POST or `mailto:` SMTP) | `--sender=` | yes |
| `dedupe` | Drop Message-ID duplicates, keep oldest | `--folder=` | yes |
| `attachments` | List large messages (v1) — strip is v2 | `--size-gt=10mb` | n/a (read-only v1) |
| `bounces` | Find bounce / auto-reply messages | `--folder=INBOX` | yes |

**Common flags:** `--json` (structured output), `--apply` (execute, default off), `--folder=` (target IMAP folder), `--limit=N` (cap operation size).

**Time syntax for `--older-than`:** `Nd` / `Nw` / `Nm` / `Ny` (days / weeks / months / years).

**Filter combinability:** `delete --sender=X --older-than=3m --apply` (AND across filters).

## Discovery report (`scan --json`)

The contract between CLI and Skill — `scan` always emits this shape:

```json
{
  "schema_version": 1,
  "scanned_at": "2026-05-04T...",
  "folder": "INBOX",
  "total_messages": 7982,
  "size_total_mb": 65.5,
  "categories": {
    "newsletters": {"count": 5649, "top_senders": [...]},
    "automated_notifications": {"count": 652, "top_senders": [...]},
    "bounces_and_autoreplies": {"count": 1, "samples": [...]},
    "large_attachments": {"count": 0, "size_mb": 0, "top_offenders": []},
    "duplicates": {"count": 18, "groups": [...]},
    "old_messages": {"older_than_12m": 196, ...},
    "by_year": {"2024": 73, "2025": 887, "2026": 7022}
  },
  "recommendations": ["...", "..."]
}
```

`schema_version` is checked by the Skill — version mismatch means update one side before continuing.

### Classification rules

| Category | Rule |
|----------|------|
| **newsletter** | `List-Unsubscribe` header present **OR** sender local-part matches `newsletter`, `noreply`, `no-reply`, `news`, `marketing` |
| **automated** | sender local-part matches `notifications`, `bot`, `service`, `alerts`, `system`, `daemon`, `automation` |
| **bounce** | sender is `MAILER-DAEMON` / `postmaster` **OR** subject starts with `Undelivered`, `Returned`, `Mail Delivery`, `Auto-Reply`, `Out of Office`, `Abwesenheits` |
| **duplicate** | identical `Message-ID` header (true dupe; fuzzy dedupe deferred to v2) |
| **large_attachment** | message size > 10 MB |

A message can fall into multiple categories.

## Audit log

Path: `~/.mailbox-cleanup/audit.log` (override with `MAILBOX_CLEANUP_AUDIT_LOG`).

Format: one JSON object per line. Example:

```json
{"timestamp":"2026-05-04T09:27:45.504Z","subcommand":"delete","args":{"sender":"service@paypal.de","older_than":"2m"},"folder":"INBOX","affected_uids":["655773","672257",...],"result":"success"}
```

Inspect with `jq`:

```bash
jq -s 'group_by(.subcommand) | map({op: .[0].subcommand, count: (map(.affected_uids|length)|add)})' ~/.mailbox-cleanup/audit.log
```

## Repo layout

```
mailbox-cleanup/
├── README.md                              ← you are here
├── pyproject.toml                         ← Python 3.11+, click, imap-tools, keyring, requests, pytest, ruff
├── src/mailbox_cleanup/
│   ├── __init__.py                        ← __version__, SCHEMA_VERSION
│   ├── cli.py                             ← click entry point
│   ├── auth.py                            ← Keychain
│   ├── imap_client.py                     ← imap-tools wrapper, retry, SSL toggle
│   ├── classify.py                        ← pure-function classification rules
│   ├── scan.py                            ← discovery → JSON report
│   ├── folders.py                         ← SPECIAL-USE folder resolver
│   ├── audit.py                           ← JSONL audit log writer
│   └── operations/
│       ├── filters.py
│       ├── delete.py
│       ├── move.py
│       ├── archive.py
│       ├── unsubscribe.py
│       ├── dedupe.py
│       ├── attachments.py
│       └── bounces.py
├── tests/                                 ← 59 tests (unit + integration via Greenmail Docker)
├── docs/
│   ├── 2026-05-04-design.md               ← spec
│   ├── 2026-05-04-implementation-plan.md  ← TDD plan
│   └── smoke-test.md                      ← read-only IONOS smoke test
├── skill/SKILL.md                         ← versioned Claude Code skill copy
└── .github/workflows/ci.yml               ← GitHub Actions
```

## Tests

```bash
uv sync --extra dev
uv run pytest -v               # 59 tests (Greenmail Docker auto-starts via conftest)
uv run ruff check .
uv run ruff format --check .
```

CI runs the same on every push. Greenmail starts on port 3143 (plain IMAP) + 3025 (SMTP).

## Limitations (v1)

1. Single mailbox only — multi-account is v2
2. IONOS only — no provider abstraction (Gmail API, Office365 = v2)
3. Strict dedupe — only by exact `Message-ID`; fuzzy hash = v2
4. Attachment listing only — in-place strip = v2
5. No hard-delete — final step is manual `Papierkorb leeren` in IONOS Webmail
6. Rule-based classification only — no ML / LLM in CLI (Skill can layer it on)
7. `auth set` requires a real TTY — no `--password-stdin` yet (v2)

## v2 backlog

- Multi-account config (`--account=`)
- Provider abstraction (Gmail API / OAuth)
- Fuzzy duplicate detection
- Attachment strip (append stripped + delete original)
- Marvin cron integration for autonomous background cleanup
- Web UI / TUI
- `--password-stdin` for non-TTY setup
- `purge-trash` hard-delete subcommand

## References

- IMAP RFC 3501, RFC 6154 (SPECIAL-USE), RFC 2369 (List-Unsubscribe), RFC 8058 (One-Click POST)
- [imap-tools](https://github.com/ikvk/imap_tools)
- [click](https://click.palletsprojects.com)
- [keyring](https://github.com/jaraco/keyring)
- [Greenmail](https://greenmail-mail-test.github.io/greenmail/) — test IMAP server

## License

Private. Personal tool — not released for general distribution.

## Author

German Rauhut · `german@rauhut.com`
