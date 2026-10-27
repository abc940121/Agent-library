#!/usr/bin/env python3
"""Checker for the library entries (standard library only)."""
import argparse
import datetime
import difflib
import re
import string
import sys
from pathlib import Path

ID_RE = re.compile(r"^E-\d{8}-[0-9a-f]{4}$")
SLUG_RE = re.compile(r"^[a-z0-9-]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
USER_RE = re.compile(r"^gh:[A-Za-z0-9][A-Za-z0-9-]*$")
GOALS = {"latency", "cost", "accuracy", "failure-rate", "tokens", "time",
         "memory", "reliability", "security", "maintainability"}
KINDS = {"fact": {"concept", "data"}, "advice": {"howto", "fix", "choice"},
         "rule": {"policy"}}
ALLOWED = {"id", "force", "kind", "layer", "kind_why", "summary", "origin", "repro",
           "source", "domain", "tags", "negative", "contradicts", "supersedes", "status",
           "expires_when", "checked_at", "added_by", "goal",
           "facts", "from", "exceptions", "holds_when", "rule_scope", "owner"}
ALWAYS = ["id", "force", "kind", "layer", "summary", "origin", "domain", "negative",
          "status", "checked_at", "added_by"]
CONFIRM_KEYS = {"entry", "verdict", "by", "checked_at", "env", "repro"}
LIST_KEYS = {"domain", "tags", "contradicts", "supersedes", "facts", "from", "env"}
NUM_WORDS = {"one", "two", "three", "four", "five", "six", "seven", "eight",
             "nine", "ten", "hundred", "thousand", "million", "half", "twice",
             "percent"}
IMPERATIVES = ("use", "do", "don't", "avoid", "always", "never", "run", "set",
               "add", "prefer")
FIX_WORDS = ("error", "crash", "timeout", "wrong output", "rejected", "hang",
             "regression")

PRIVACY = [
    ("windows drive path", re.compile(r"\b[A-Za-z]:[\\/]")),
    ("unc path", re.compile(r"\\\\[A-Za-z0-9]")),
    ("internal repo path", re.compile(r"a2a/outputs|\.scratch/")),
    ("private github url", re.compile(r"github\.com\S*-private")),
    ("long hex string", re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{32,}(?![0-9A-Fa-f])")),
    ("secret-like token", re.compile(
        r"sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN")),
    ("long hex string", re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{32,}(?![0-9A-Fa-f])")),
]
# 40+ chars with letters and digits; "/" is left out so URL paths do not match.
LONG_TOKEN = re.compile(r"[A-Za-z0-9+_=-]{40,}")
REPO_URL = re.compile(
    r"(?:github\.com|gitlab\.com|bitbucket\.org)/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
LONG_TOKEN = re.compile(r"[A-Za-z0-9+_=-]{40,}")
REPO_URL = re.compile(r"(?:github\.com|gitlab\.com|bitbucket\.org)/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
IPV4 = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.]*\d)")


def parse_list(val):
    v = val.strip()
    if not (v.startswith("[") and v.endswith("]")):
        return None
    inner = v[1:-1].strip()
    if not inner:
        return []
    return [x.strip() for x in inner.split(",")]


def parse_entry(text, problems, name, allowed=None):
    """Return (fields dict, key->line dict, body)."""
    lines = text.split("\n")
    fields, where = {}, {}
    if not lines or lines[0].strip() != "---":
        problems.append((name, 1, "front matter must start with ---"))
        return fields, where, ""
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        problems.append((name, 1, "front matter is not closed with ---"))
        return fields, where, ""
    for i in range(1, end):
        raw = lines[i].rstrip("\r")
        if not raw.strip():
            continue
        if ":" not in raw:
            problems.append((name, i + 1, "front matter line is not key: value"))
            continue
        k, v = raw.split(":", 1)
        k, v = k.strip(), v.strip()
        if k in fields:
            problems.append((name, i + 1, f"duplicate key {k}"))
            continue
        where[k] = i + 1
        if k not in (ALLOWED if allowed is None else allowed):
            problems.append((name, i + 1, f"unknown key {k}"))
        if k in LIST_KEYS:
            lst = parse_list(v)
            if lst is None:
                problems.append((name, i + 1, f"{k} must be a list like [a, b]"))
                lst = []
            fields[k] = lst
        else:
            fields[k] = v
    body = "\n".join(lines[end + 1:])
    return fields, where, body


def strip_tokens(s):
    s = re.sub(r"\b\d+(?:\.(?:\d+|x))+\b", " ", s)
    s = re.sub(r"\S*(?:[A-Za-z]\S*\d|\d\S*[A-Za-z])\S*", " ", s)
    return s


def has_number(s):
    if re.search(r"\d", s):
        return True
    words = set(re.findall(r"[a-z]+", s.lower()))
    return bool(words & NUM_WORDS)


def check_summary(kind, summary, add):
    low = summary.lower()
    stripped = strip_tokens(summary)
    first = re.findall(r"[a-z']+", low)[:1]
    if kind in ("concept", "data") and first and first[0] in IMPERATIVES:
        add("summary", f"{kind} summary must not start with an imperative ({first[0]})")
    if kind == "concept" and has_number(stripped):
        add("summary", "concept summary must not contain a number")
    elif kind == "data" and not has_number(stripped):
        add("summary", "data summary must contain a number")
    elif kind == "howto":
        if not (summary.startswith("To ") and ", " in summary):
            add("summary", "howto summary must start with 'To ' and contain ', '")
    elif kind == "fix":
        ok = summary.startswith("When ") and ", " in summary
        if ok:
            clause = summary.split(", ", 1)[0].lower()
            ok = any(w in clause for w in FIX_WORDS)
        if not ok:
            add("summary", "fix summary must start with 'When ' and name a failure "
                "(error, crash, timeout, wrong output, rejected, hang, regression) before the first ', '")
    elif kind == "choice":
        if not (summary.startswith("For ") and " over " in summary and " because " in summary):
            add("summary", "choice summary must start with 'For ' and contain ' over ' and ' because '")
    elif kind == "policy":
        if not (summary.startswith("In ") and (" must " in summary or " must not " in summary)):
            add("summary", "policy summary must start with 'In ' and contain ' must ' or ' must not '")


def load_scopes(root, problems):
    scopes = {}
    p = root / "SCOPES.tsv"
    if not p.exists():
        problems.append(("SCOPES.tsv", 0, "file is missing"))
        return scopes
    rows = p.read_text(encoding="utf-8").splitlines()
    if not rows or rows[0].split("\t") != ["scope", "owners"]:
        problems.append(("SCOPES.tsv", 1, "header must be 'scope<TAB>owners'"))
    for row in rows[1:]:
        if not row.strip():
            continue
        parts = row.split("\t")
        scopes[parts[0].strip()] = parts[1].split() if len(parts) > 1 else []
    return scopes


def load_public_repos(root):
    p = root / "PUBLIC_REPOS.txt"
    if not p.is_file():
        return set()
    lines = p.read_text(encoding="utf-8").splitlines()
    return {x.strip().lower() for x in lines if x.strip() and not x.startswith("#")}


def privacy(text, name, problems, public_repos=frozenset()):
    for n, line in enumerate(text.split("\n"), 1):
        for label, rx in PRIVACY:
            if rx.search(line):
                problems.append((name, n, f"privacy: {label}"))
        for m in LONG_TOKEN.finditer(line):
            t = m.group(0)
            if any(c.isdigit() for c in t) and any(c.isalpha() for c in t):
                problems.append((name, n, "privacy: long token-like string"))
                break
        for m in REPO_URL.finditer(line):
            repo = f"{m.group(1)}/{m.group(2)}".lower().removesuffix(".git")
            if repo not in public_repos:
                problems.append((name, n, "privacy: repo link not in PUBLIC_REPOS.txt"))
        for m in IPV4.finditer(line):
            octs = [int(x) for x in m.groups()]
            if all(o <= 255 for o in octs) and m.group(0) not in ("127.0.0.1", "0.0.0.0"):
                problems.append((name, n, "privacy: ipv4 address"))


def normalise_summary(summary):
    summary = summary.lower().translate(str.maketrans("", "", string.punctuation))
    return " ".join(summary.split())


def near_duplicate_pairs(parsed, threshold):
    items = [(stem, normalise_summary(fields.get("summary", "")))
             for stem, (_, fields, _, _) in sorted(parsed.items())]
    for i, (id1, summary1) in enumerate(items):
        for id2, summary2 in items[i + 1:]:
            matcher = difflib.SequenceMatcher(None, summary1, summary2)
            if matcher.real_quick_ratio() < threshold or matcher.quick_ratio() < threshold:
                continue
            ratio = matcher.ratio()
            if ratio >= threshold:
                yield id1, id2, ratio, summary1, summary2


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--write-index", action="store_true")
    ap.add_argument("--similar", type=float, metavar="THRESHOLD")
    args = ap.parse_args(argv)
    root = Path(args.root)
    problems = []
    scopes = load_scopes(root, problems)
    public_repos = load_public_repos(root)
    files =sorted((root / "entries").glob("*.md")) if (root / "entries").is_dir() else []
    parsed = {}
    for f in files:
        name = f"entries/{f.name}"
        text = f.read_text(encoding="utf-8")
        privacy(text, name, problems, public_repos)
        fields, where, body = parse_entry(text, problems, name)
        parsed[f.stem] = (name, fields, where, body)
        if not ID_RE.match(f.stem):
            problems.append((name, 0, "file name must be <ID>.md with ID like E-20261026-ab12"))
    if args.similar is not None:
        if not 0 <= args.similar <= 1:
            ap.error("--similar must be between 0 and 1")
        pairs = sorted(near_duplicate_pairs(parsed, args.similar),
                       key=lambda pair: (-pair[2], pair[0], pair[1]))
        for id1, id2, ratio, summary1, summary2 in pairs:
            print(f"{ratio:.2f}\t{id1}\t{id2}\t{summary1}\t{summary2}")
        return 0
    forces = {s: p[1].get("force") for s, p in parsed.items()}

    confirmations = {stem: {} for stem in parsed}
    confirm_re = re.compile(r"^([A-Za-z0-9][A-Za-z0-9-]*)-(\d{8})-[0-9a-f]{4}\.md$")
    today = datetime.date.today()
    confirm_dir = root / "confirms"
    if confirm_dir.is_dir():
        for f in sorted(confirm_dir.glob("*/*.md")):
            name = f.relative_to(root).as_posix()
            match = confirm_re.fullmatch(f.name)
            entry_id = f.parent.name
            if not match:
                problems.append((name, 0, "file name must be <gh-user>-YYYYMMDD-xxxx.md")); continue
            user, compact_date = match.groups()
            text = f.read_text(encoding="utf-8")
            privacy(text, name, problems, public_repos)
            F, W, body = parse_entry(text, problems, name, CONFIRM_KEYS)[0:3]
            def add(key, msg, name=name, W=W):
                problems.append((name, W.get(key, 0), f"{key}: {msg}" if key else msg))
            if entry_id not in parsed: add(None, f"entry {entry_id} does not exist")
            if F.get("entry") != entry_id: add("entry", f"must equal folder name {entry_id}")
            if F.get("verdict") not in ("confirm", "dispute"): add("verdict", "must be confirm or dispute")
            if F.get("by") != f"gh:{user}": add("by", f"must equal gh:{user}")
            if not DATE_RE.match(F.get("checked_at", "")): add("checked_at", "must be YYYY-MM-DD")
            else:
                try:
                    checked = datetime.date.fromisoformat(F["checked_at"])
                    if checked > today: add("checked_at", "must not be in the future")
                except ValueError: add("checked_at", "must be a real date")
                if F["checked_at"].replace("-", "") != compact_date: add("checked_at", "must equal the date in the file name")
            env = F.get("env", [])
            if not isinstance(env, list) or not 1 <= len(env) <= 3 or any(not SLUG_RE.match(x) for x in env): add("env", "needs 1-3 lowercase slugs")
            if F.get("verdict") == "dispute" and not F.get("repro", "").strip(): add("repro", "dispute needs non-empty repro")
            if not body.strip(): add(None, "body must not be empty")
            if entry_id in parsed and F.get("by") and F.get("checked_at"):
                confirmations[entry_id].setdefault(F["by"], []).append(
                    (F["checked_at"], F.get("verdict"), name, F.get("env", [])))

    for stem, (name, F, W, body) in parsed.items():
        def add(key, msg, name=name, W=W):
            problems.append((name, W.get(key, 0), f"{key}: {msg}" if key else msg))

        for k in ALWAYS:
            if not F.get(k):
                add(None, f"missing required field {k}")
        if not body.strip():
            problems.append((name, 0, "body must not be empty"))
        if F.get("id") and F["id"] != stem:
            add("id", f"id {F['id']} does not match file name {stem}")
        force, kind = F.get("force"), F.get("kind")
        if force and force not in KINDS:
            add("force", "must be fact, advice or rule")
            force = None
        if kind:
            if kind == "other":
                if not F.get("kind_why", "").strip():
                    add("kind", "kind other needs a non-empty kind_why")
            elif force and kind not in KINDS[force]:
                add("kind", f"kind {kind} does not fit force {force}")
            elif not force and not any(kind in v for v in KINDS.values()):
                add("kind", f"unknown kind {kind}")
        summ = F.get("summary", "")
        if summ:
            if not 20 <= len(summ) <= 200:
                add("summary", f"length {len(summ)} must be 20-200")
            if kind and kind != "other":
                check_summary(kind, summ, add)
        origin = F.get("origin")
        if origin:
            if origin not in ("measured", "quoted", "guess"):
                add("origin", "must be measured, quoted or guess")
            elif origin == "measured" and not F.get("repro", "").strip():
                add("origin", "measured needs non-empty repro")
            elif origin == "quoted" and not F.get("source", "").startswith("https://"):
                add("origin", "quoted needs source starting with https://")
        for key, lo, hi in (("domain", 1, 2), ("tags", 0, 3)):
            if key in F:
                lst = F[key]
                if not lo <= len(lst) <= hi:
                    add(key, f"needs {lo}-{hi} items")
                for x in lst:
                    if not SLUG_RE.match(x):
                        add(key, f"item '{x}' must be a lowercase slug")
        if F.get("negative") and F["negative"] not in ("yes", "no"):
            add("negative", "must be yes or no")
        if F.get("status") and F["status"] not in ("settled", "open"):
            add("status", "must be settled or open")
        layer = F.get("layer")
        if layer and layer not in ("raw", "info", "critical", "law"):
            add("layer", "must be raw, info, critical or law")
        for key in ("exceptions", "holds_when"):
            if key in F and not 10 <= len(F[key]) <= 300:
                add(key, "must be one line of 10-300 characters")
        if layer == "critical" and not F.get("exceptions", "").strip():
            add("exceptions", "critical needs non-empty exceptions")
        if layer == "law" and not F.get("holds_when", "").strip():
            add("holds_when", "law needs non-empty holds_when")
        if layer != "law" and "holds_when" in F:
            add("holds_when", "only allowed on law entries")
        if layer == "law" and "exceptions" in F:
            add("exceptions", "not allowed on law entries")
        if F.get("checked_at") and not DATE_RE.match(F["checked_at"]):
            add("checked_at", "must be YYYY-MM-DD")
        if F.get("added_by") and not USER_RE.match(F["added_by"]):
            add("added_by", "must be gh:<github-user>")
        for x in F.get("contradicts", []):
            if x not in parsed:
                add("contradicts", f"{x} does not exist")
        for x in F.get("supersedes", []):
            if x not in parsed:
                add("supersedes", f"{x} does not exist")
            elif x == stem:
                add("supersedes", "must not list itself")
        evidence = set(F.get("from", [])) | set(F.get("facts", []))
        for x in F.get("from", []):
            if x not in parsed:
                add("from", f"{x} does not exist")
            elif x == stem:
                add("from", "must not list itself")
        if layer == "info" and not evidence:
            add("layer", "info needs at least 1 evidence id")
        if layer == "critical":
            info_evidence = [x for x in evidence if x in parsed and parsed[x][1].get("layer") == "info"]
            if len(evidence) < 2 or len(info_evidence) < 2:
                add("layer", "critical needs at least 2 evidence ids whose entries are layer: info")
            confirms = confirmations.get(stem, {})
            current = {u: max(rs, key=lambda x: (x[0], x[2])) for u, rs in confirms.items()
                       if u != F.get("added_by")}
            if F.get("status") == "settled" and sum(v[1] == "confirm" for v in current.values()) < 2:
                add("status", "a critical entry needs 2 confirms from other users before settled")
            if F.get("status") != "settled" and sum(v[1] == "confirm" for v in current.values()) >= 2:
                pass
        if layer == "law":
            critical_evidence = [x for x in evidence if x in parsed and
                                 parsed[x][1].get("layer") in ("critical", "law")]
            if len(evidence) < 2 or len(critical_evidence) < 2:
                add("layer", "law needs at least 2 evidence ids whose entries are layer: critical or law")
            confirms = confirmations.get(stem, {})
            current = {u: max(rs, key=lambda x: (x[0], x[2])) for u, rs in confirms.items()
                       if u != F.get("added_by")}
            confirmers = [v for v in current.values() if v[1] == "confirm"]
            envs = {env for v in confirmers for env in v[3]}
            disputes = sum(v[1] == "dispute" for v in current.values())
            if F.get("status") == "settled" and (len(confirmers) < 3 or len(envs) < 2):
                add("status", "a law entry needs 3 confirms from other users across 2 envs before settled")
            if F.get("status") == "settled" and disputes:
                add("status", "a law with a dispute must be open; fix it or move it back to critical")
        if layer == "raw" and origin == "measured" and F.get("status") == "settled":
            confirms = confirmations.get(stem, {})
            current = {u: max(rs, key=lambda x: (x[0], x[2])) for u, rs in confirms.items()
                       if u != F.get("added_by")}
            if sum(v[1] == "confirm" for v in current.values()) < 1:
                add("status", "a raw measured entry needs 1 confirm from another user before settled")
        if force == "advice":
            goal = F.get("goal", "")
            # a fix's goal is the symptom gone, so it may say goal: symptom
            if not goal:
                add(None, "advice needs goal")
            elif goal not in GOALS and not (kind == "fix" and goal == "symptom"):
                add("goal", f"goal {goal} is not one of the allowed goals")
            facts = F.get("facts", [])
            if kind in ("howto", "choice") and not facts:
                add(None, f"{kind} needs at least one fact in facts")
            for x in facts:
                if x not in parsed:
                    add("facts", f"{x} does not exist")
                elif forces.get(x) != "fact":
                    add("facts", f"{x} is not a fact entry")
        else:
            for k in ("goal", "facts"):
                if k in F:
                    add(k, "only allowed on advice entries")
        if force == "rule":
            sc, ow = F.get("rule_scope", ""), F.get("owner", "")
            if not sc:
                add(None, "rule needs rule_scope")
            elif sc not in scopes:
                add("rule_scope", f"scope {sc} is not in SCOPES.tsv")
            if not ow:
                add(None, "rule needs owner")
            elif sc in scopes and ow not in scopes[sc]:
                add("owner", f"owner {ow} is not listed for scope {sc}")
        else:
            for k in ("rule_scope", "owner"):
                if k in F:
                    add(k, "only allowed on rule entries")

    for id1, id2, ratio, _, _ in near_duplicate_pairs(parsed, 0.85):
        fields1, fields2 = parsed[id1][1], parsed[id2][1]
        links1 = set(fields1.get("contradicts", [])) | set(fields1.get("supersedes", []))
        links2 = set(fields2.get("contradicts", [])) | set(fields2.get("supersedes", []))
        if id2 not in links1 and id1 not in links2:
            name, where = parsed[id2][0], parsed[id2][2]
            problems.append((name, where.get("summary", 0),
                             f"summary: near-duplicate of {id1} (ratio {ratio:.2f}); "
                             "merge, or link it with contradicts/supersedes"))

    def clean(s):
        return s.replace("\t", " ")

    rows = ["id\tforce\tkind\tlayer\tdomain\ttags\tsummary\tconfirms\tdisputes\tlast_checked"]
    for stem in sorted(parsed):
        F = parsed[stem][1]
        votes = confirmations.get(stem, {})
        current = {u: max(rs, key=lambda x: (x[0], x[2])) for u, rs in votes.items() if u != F.get("added_by")}
        dates = [F.get("checked_at", "")] + [v[0] for v in current.values() if DATE_RE.match(v[0])]
        rows.append("\t".join([
            stem, clean(F.get("force", "")), clean(F.get("kind", "")), clean(F.get("layer", "")),
            ",".join(F.get("domain", [])), ",".join(F.get("tags", [])),
            clean(F.get("summary", "")), str(sum(v[1] == "confirm" for v in current.values())),
            str(sum(v[1] == "dispute" for v in current.values())), max(dates)]))
    index = "\n".join(rows) + "\n"
    ip = root / "INDEX.tsv"
    if args.write_index:
        with open(ip, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(index)
    elif not ip.exists():
        problems.append(("INDEX.tsv", 0, "missing; run with --write-index"))
    elif ip.read_bytes() != index.encode("utf-8"):
        problems.append(("INDEX.tsv", 0, "stale; run with --write-index"))

    if problems:
        for name, line, msg in problems:
            print(f"{name}:{line}: {msg}")
        return 1
    print(f"OK {len(parsed)} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
