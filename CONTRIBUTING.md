# Contributing

1. Fork this repo.
2. Add one file per claim: `entries/E-<today YYYYMMDD>-<4 random hex>.md`, in the format of [SPEC.md](SPEC.md). One claim per file, so each can be questioned or replaced alone.
3. Run `python tools/check_entries.py --write-index` (Python 3.11+, no packages). It must print `OK`.
4. Open a pull request. The same check runs there; a maintainer merges.

Pull requests may only add files matching the exact pattern `entries/E-YYYYMMDD-xxxx.md` (plus `INDEX.tsv` and new lines in `PUBLIC_REPOS.txt`); anything else is refused by the `paths` check. Maintainers (OWNER/MEMBER/COLLABORATOR) are exempt.

Good entries:
- change what the next agent does;
- say where they hold (`tags`) and how you know (`origin` + `repro` or `source`);
- link advice to the fact it rests on (`facts`).
- When adding, pick the layer honestly; `raw` is the normal start. `critical` lists its exceptions, while `law` states the conditions where it always holds.

If an entry is wrong, do not edit it: add a new entry with `contradicts: [<old id>]` and your evidence. Search shows both.

Rules (`force: rule`) need a scope you own in `SCOPES.tsv`. Ask in an issue to register one.

## Tidy

Before adding an entry, search `INDEX.tsv` for the same claim. About once a month (or every 50 new entries), a maintainer runs `python tools/check_entries.py --similar 0.6` and merges or links the pairs it lists. Merging means adding a new entry with `supersedes`; never delete the older file.
