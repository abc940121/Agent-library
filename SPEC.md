# Entry spec (v1)

`tools/check_entries.py` enforces everything on this page. If this page and the checker disagree, open an issue.

## File
`entries/<ID>.md`. ID = `E-YYYYMMDD-xxxx` (date added, 4 random hex digits). Front matter between two `---` lines (`key: value`, lists as `[a, b]`), then a non-empty markdown body.

```
---
id: E-20261026-1234
force: fact
kind: concept
summary: Python's -I flag makes the interpreter ignore all PYTHON* environment variables.
origin: quoted
source: https://docs.python.org/3/using/cmdline.html#cmdoption-I
domain: [python]
tags: [windows]
negative: no
status: settled
checked_at: 2026-10-26
added_by: gh:your-github-user
---
Body: the detail, the condition it holds under, and how to check it.
```

## Fields
| field | required | values |
|---|---|---|
| id | always | equals the file name |
| force | always | fact, advice, rule |
| kind | always | fact: concept or data. advice: howto, fix or choice. rule: policy. Or `other` with `kind_why`. |
| summary | always | one line, 20-200 characters, in the kind's template |
| origin | always | measured (needs `repro`), quoted (needs `source`, an https link), guess |
| domain | always | 1-2 lowercase slugs |
| tags | optional | 0-3 lowercase slugs: where the claim holds (windows, n8n, bash...) |
| negative | always | yes if the claim says something does NOT work |
| contradicts | optional | IDs of entries with the same subject and the opposite claim |
| status | always | settled or open; `expires_when` optional |
| checked_at | always | YYYY-MM-DD |
| added_by | always | `gh:<github-user>` |
| goal | advice | one of: latency, cost, accuracy, failure-rate, tokens, time, memory, reliability, security, maintainability. A fix may use `symptom`. |
| facts | advice | IDs of fact entries the advice rests on; at least one for howto and choice |
| rule_scope, owner | rule | the scope must be in `SCOPES.tsv` and the owner listed for it |

## Summary templates
| kind | force | template |
|---|---|---|
| concept | fact | "X is/means Y", "X happens because Y", "X can/does/cannot Y [under E]". No measured number. |
| data | fact | a measured number with a unit or a comparison |
| howto | advice | "To <goal>, do X [when E]" |
| fix | advice | "When <failure>, do R [because C]"; failure is one of: error, crash, timeout, wrong output, rejected, hang, regression |
| choice | advice | "For <goal>, A over B because ..."; B is a named alternative |
| policy | rule | "In <rule_scope>, must / must not X" |

- Numbers inside names and versions (Qwen3, GPT-6, n8n, 2.x) do not count as measured numbers.
- A comparison: a measured number makes it data; else "For <goal> ... because" makes it choice; else concept.
- Only advice and rules may be imperative.
- "X can improve Y" is two entries: a fact for the claim, and a howto that links to it.

## What is not an entry
- To-dos and current state ("the quota is used up now"). They change; put them in an issue.
- Anything that expires within 14 days.
- Private paths, private addresses, secrets. The checker rejects drive paths, private IPs, private repo links and key-shaped strings.

## Computed later (not written by hand)
Trust (independent confirmations) and freshness (newest confirmation). Not in v1.
