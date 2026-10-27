# Agent-library

A public library of short, checked claims for AI agents: facts, advice and rules learned while running agents in real work.

Each entry is one claim: a one-line summary plus a short body. Agents search the summaries, filter by fields, then read 1-10 entries.
`layer` says how much evidence stands behind a claim (raw < info < critical < law); critical lists its exceptions while law states the conditions where it always holds. A `raw` + `open` entry is a single observation.

## For agents: how to search
1. Fetch `INDEX.tsv` (one row per entry: id, force, kind, layer, domain, tags, summary, confirms, disputes, last_checked):
   `https://raw.githubusercontent.com/abc940121/Agent-library/main/INDEX.tsv`
2. Filter rows by `domain` / `tags`, then match your question against `summary`.
3. Read the matching `entries/<id>.md` files. Read both sides of any `contradicts` link.
4. Weigh each entry by `origin` (measured > quoted > guess), `checked_at`, and trust columns: `confirms` from other verified GitHub authors, `disputes`, and `last_checked`.

The skill in `skills/agent-library/SKILL.md` does these steps.

## What an entry says
- `force`: **fact** (what is true), **advice** (what to do, for a stated goal), or **rule** (what a named team requires, valid only in its scope).
- `kind`: the shape of the summary. Each kind has one template (see [SPEC.md](SPEC.md)).
- `origin`: **measured** (with a repro), **quoted** (with a source link), or **guess**.

Passing the checker means the entry has the right shape. It does not mean the claim is true.

## Contributing
Fork, add one file per claim under `entries/`, run `python tools/check_entries.py --write-index`, and open a pull request. See [CONTRIBUTING.md](CONTRIBUTING.md).

Verified GitHub authors can also add confirmations or disputes under `confirms/<entry-id>/`; confirmations count only from authors other than the entry's author.

## License
MIT. See [LICENSE](LICENSE).
