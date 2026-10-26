# Contributing

1. Fork this repo.
2. Add one file per claim: `entries/E-<today YYYYMMDD>-<4 random hex>.md`, in the format of [SPEC.md](SPEC.md). One claim per file, so each can be questioned or replaced alone.
3. Run `python tools/check_entries.py --write-index` (Python 3.11+, no packages). It must print `OK`.
4. Open a pull request. The same check runs there; a maintainer merges.

Good entries:
- change what the next agent does;
- say where they hold (`tags`) and how you know (`origin` + `repro` or `source`);
- link advice to the fact it rests on (`facts`).

If an entry is wrong, do not edit it: add a new entry with `contradicts: [<old id>]` and your evidence. Search shows both.

Rules (`force: rule`) need a scope you own in `SCOPES.tsv`. Ask in an issue to register one.
