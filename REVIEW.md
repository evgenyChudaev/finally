# Review: Changes Since Last Commit

## Findings

### High: Quick Start points to files and directories that do not exist

[README.md](C:/Users/eugen/Desktop/Projects/finally/README.md:31) tells users to copy `.env.example`, but this file is not present in the working tree. [README.md](C:/Users/eugen/Desktop/Projects/finally/README.md:32) and [README.md](C:/Users/eugen/Desktop/Projects/finally/README.md:34) then tell users to run `./scripts/start.sh` or `./scripts/start.ps1`, but there is no `scripts/` directory. [README.md](C:/Users/eugen/Desktop/Projects/finally/README.md:39) also says the SQLite database is bind-mounted at `./db/finally.db`, while `db/` is absent too. The plan repeats these as existing project artifacts at [planning/PLAN.md](C:/Users/eugen/Desktop/Projects/finally/planning/PLAN.md:96) through [planning/PLAN.md](C:/Users/eugen/Desktop/Projects/finally/planning/PLAN.md:103).

This makes the documented primary startup path fail before Docker is reached.

Recommendation: add `.env.example`, `scripts/start.sh`, `scripts/stop.sh`, `scripts/start.ps1`, `scripts/stop.ps1`, and `db/.gitkeep`, or keep the README on the direct Docker command until those artifacts exist.

### High: Stop hook is declared twice and can run the reviewer twice

[.claude/settings.json](C:/Users/eugen/Desktop/Projects/finally/.claude/settings.json:2) defines a `Stop` hook that runs `codex exec "Review changes since last commit and write results to a file named REVIEW.md"`. The same command is also declared by the newly added plugin hook at [independent-reviewer/hooks/hooks.json](C:/Users/eugen/Desktop/Projects/finally/independent-reviewer/hooks/hooks.json:3), and the plugin is enabled in shared settings at [.claude/settings.json](C:/Users/eugen/Desktop/Projects/finally/.claude/settings.json:14).

If Claude loads both project hooks and enabled-plugin hooks, every assistant stop will launch two independent reviewers against the same working tree and the same `REVIEW.md` path. That is slow, noisy, and risks last-writer-wins output.

Recommendation: put the hook in one place only. Prefer the plugin hook if the plugin is the intended reusable unit, and remove the duplicate top-level `hooks` block from `.claude/settings.json`.

### High: Unknown ticker validation blocks adding valid new tickers

[planning/PLAN.md](C:/Users/eugen/Desktop/Projects/finally/planning/PLAN.md:272) defines an unknown ticker as one with no entry in the price cache, while [planning/PLAN.md](C:/Users/eugen/Desktop/Projects/finally/planning/PLAN.md:291) says `POST /api/watchlist` rejects unknown tickers. That makes adding a valid new ticker impossible in the normal flow: the price cache is populated from tracked symbols, so a symbol is absent until after it has already been added. Massive mode has the same issue unless the symbol happened to be fetched earlier.

Recommendation: separate ticker validation from the live price cache. For example, `validate_ticker()` can check a simulator allowlist or perform a Massive lookup, then adding the ticker can seed the first cached price.

### High: Event-driven portfolio snapshots do not track market P&L over time

[planning/PLAN.md](C:/Users/eugen/Desktop/Projects/finally/planning/PLAN.md:237) now records `portfolio_snapshots` only after trades and once at app startup, but [planning/PLAN.md](C:/Users/eugen/Desktop/Projects/finally/planning/PLAN.md:405) still promises a P&L chart showing total portfolio value over time. Portfolio value changes whenever market prices move, not only when cash changes. With this contract, a user can buy shares, watch prices stream for minutes, and see no P&L history movement until another trade or restart.

Recommendation: restore periodic snapshots, compute the chart from live prices on the frontend, or rename/narrow the chart to cash-event snapshots instead of total portfolio value over time.

### Medium: SSE delta contract is underspecified for multiple price writes

[planning/PLAN.md](C:/Users/eugen/Desktop/Projects/finally/planning/PLAN.md:189) says the SSE handler emits deltas when the cache version advances, while [planning/PLAN.md](C:/Users/eugen/Desktop/Projects/finally/planning/PLAN.md:277) documents a single-ticker event payload. A monotonic cache version only says that something changed; it does not identify which ticker changed or preserve multiple writes that may occur between a client's sends. With only latest prices in cache, the handler cannot reliably emit true deltas.

Recommendation: either send a full snapshot when the version changes, or define cache support for `changes_since(version)` with per-update sequence numbers and a batched SSE payload.

### Medium: Bind-mounted database path is missing from ignore rules

[README.md](C:/Users/eugen/Desktop/Projects/finally/README.md:39) and [planning/PLAN.md](C:/Users/eugen/Desktop/Projects/finally/planning/PLAN.md:444) switch persistence to a host `db/` bind mount, and [planning/PLAN.md](C:/Users/eugen/Desktop/Projects/finally/planning/PLAN.md:103) says `db/.gitkeep` exists and `finally.db` is gitignored. The working tree has no `db/` directory, and [.gitignore](C:/Users/eugen/Desktop/Projects/finally/.gitignore:61) only ignores `db.sqlite3`, not `db/finally.db` or SQLite sidecar files under `db/`.

Recommendation: add `db/.gitkeep` and ignore the runtime files explicitly, for example `db/finally.db`, `db/*.db`, `db/*.db-wal`, and `db/*.db-shm`.

### Low: Shared Claude settings dropped existing enabled plugins

[.claude/settings.json](C:/Users/eugen/Desktop/Projects/finally/.claude/settings.json:14) now enables only `independent-reviewer@evg-tools`. The diff removes the previously enabled `frontend-design`, `context7`, and `playwright` plugins from shared settings. If those plugins are expected for the agent workflow, this is a regression unrelated to the review hook.

Recommendation: preserve the existing `enabledPlugins` entries alongside the new reviewer plugin unless disabling those plugins is intentional.

### Low: Local Claude permission file should probably stay untracked

[.claude/settings.local.json](C:/Users/eugen/Desktop/Projects/finally/.claude/settings.local.json:1) is untracked and grants `Bash(codex exec *)`. Local permission files are usually machine-specific, and committing this would share an automation permission that may not be appropriate for every checkout.

Recommendation: add `.claude/settings.local.json` to `.gitignore`, or move the permission into shared settings only if it is deliberately project-wide.

## Notes

- I did not run tests. The reviewed changes are documentation and Claude/plugin configuration only.
- Git required a per-command `safe.directory` override because the checkout is owned by a different Windows account under the sandbox user.
- Git also emitted warnings about `C:\Users\eugen/.config/git/ignore` being inaccessible under the sandbox user; this did not prevent reading the repository diff.
