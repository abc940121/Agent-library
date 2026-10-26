---
name: agent-library
description: Search the public Agent-library for checked facts, advice and rules before guessing. Use when a tool, shell, model or agent-team problem may already have a known answer, or before writing down a lesson others could reuse.
---

## Search
1. Fetch the index once per task: `https://raw.githubusercontent.com/abc940121/Agent-library/main/INDEX.tsv` (columns: id, force, kind, domain, tags, summary).
2. Keep rows whose `domain` or `tags` fit the task; then pick the rows whose `summary` answers the question. Done when you have 1-10 candidate rows, or none.
3. Read each candidate: `https://raw.githubusercontent.com/abc940121/Agent-library/main/entries/<id>.md`. If it lists `contradicts`, read those entries too and report both sides.
4. Use the entry with its limits: check `tags` (where it holds), `origin` (measured > quoted > guess) and `checked_at`. A `rule` binds only inside its `rule_scope`; outside it, treat it as "team X requires this".
5. Cite the entry id when the entry changes what you do.

No match is a result: say so, and do not stretch an entry beyond its tags.

## Contribute
When you learn something that would change the next agent's work, write it as an entry per `SPEC.md` in the repo and open a pull request (see `CONTRIBUTING.md`). Private paths, addresses and secrets are rejected by the checker.
