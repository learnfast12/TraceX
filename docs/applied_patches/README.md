# Applied Patches (Historical Record)

Scripts in this directory are **one-shot patch scripts that have already been
applied and committed**. They are kept for audit trail / judge Q&A only —
do NOT re-run them against the current codebase. Each contains `assert()`
checks against exact string matches that existed at patch time; running
against post-patch code will raise `AssertionError`, not silently no-op.

| Script | Applied in commit | What it did |
|---|---|---|
| `apply_fixes_670f0a9_ALREADY_APPLIED.sh` | `670f0a9` | Added peel-sink wallet seeding + IP cross-reference seed path for single-tx ransomware collectors. Closed recall gap 0.9194 -> 0.9959. |
