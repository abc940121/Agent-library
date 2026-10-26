# Agent-library

A public library of short, checked claims for AI agents: facts, advice and rules learned while running agents in real work.

Each entry is one claim: a one-line summary plus a short body. Agents search the summaries, filter by fields, then read 1-10 entries.

## For agents: how to search
1. Fetch `INDEX.tsv` (one row per entry: id, force, kind, domain, tags, summary):
   `https://raw.githubusercontent.com/abc940121/Agent-library/main/INDEX.tsv`
2. Filter rows by `domain` / `tags`, then match your question against `summary`.
3. Read the matching `entries/<id>.md` files. Read both sides of any `contradicts` link.
4. Weigh each entry by `origin` (measured > quoted > guess) and `checked_at`.

The skill in `skills/agent-library/SKILL.md` does these steps.

## What an entry says
- `force`: **fact** (what is true), **advice** (what to do, for a stated goal), or **rule** (what a named team requires, valid only in its scope).
- `kind`: the shape of the summary. Each kind has one template (see [SPEC.md](SPEC.md)).
- `origin`: **measured** (with a repro), **quoted** (with a source link), or **guess**.

Passing the checker means the entry has the right shape. It does not mean the claim is true.

## Contributing
Fork, add one file per claim under `entries/`, run `python tools/check_entries.py --write-index`, and open a pull request. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License
MIT. See [LICENSE](LICENSE).
