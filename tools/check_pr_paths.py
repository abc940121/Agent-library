#!/usr/bin/env python3
import argparse, json, re, sys
from pathlib import Path

ENTRY_RE = re.compile(r"^entries/E-[0-9]{8}-[0-9a-f]{4}\.md$")
CONFIRM_RE = re.compile(r"^confirms/(E-[0-9]{8}-[0-9a-f]{4})/([A-Za-z0-9][A-Za-z0-9-]*)-[0-9]{8}-[0-9a-f]{4}\.md$")
STATUSES = {"added", "modified", "removed", "renamed"}

def refusal(status, path, reason):
    return f"REFUSED {status} {path!r}: {reason}"

def unsafe(path):
    return (not isinstance(path, str) or any(ord(c) < 32 or ord(c) == 127 for c in path)
            or "\\" in path or ".." in path or path.startswith("/") or path.endswith(" "))

def append_only(base_path, head_path):
    if base_path is None or head_path is None:
        return False, "PUBLIC_REPOS.txt requires base and head files"
    try:
        base, head = base_path.read_bytes(), head_path.read_bytes()
    except OSError as exc:
        return False, f"cannot read PUBLIC_REPOS.txt data: {exc}"
    if not head.startswith(base):
        return False, "PUBLIC_REPOS.txt must retain the exact base prefix"
    rest = head[len(base):]
    if base and not base.endswith(b"\n") and rest[:1] != b"\n":
        return False, "PUBLIC_REPOS.txt base line must remain intact"
    if not rest or not rest.endswith(b"\n"):
        return False, "PUBLIC_REPOS.txt additions must be complete lines"
    return True, ""

def arrays(path):
    text = path.read_text(encoding="utf-8")
    decoder, pos, result = json.JSONDecoder(), 0, []
    while pos < len(text):
        while pos < len(text) and text[pos].isspace(): pos += 1
        if pos == len(text): break
        value, pos = decoder.raw_decode(text, pos)
        if not isinstance(value, list): raise ValueError("API input must contain JSON arrays")
        result.extend(value)
    return result

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--maintainer", action="store_true")
    ap.add_argument("--files-json", type=Path)
    ap.add_argument("--expected-count", type=int)
    ap.add_argument("--public-repos-base", type=Path)
    ap.add_argument("--public-repos-head", type=Path)
    ap.add_argument("--author")
    a = ap.parse_args(argv)
    if a.maintainer: print("OK (maintainer)"); return 0
    if a.files_json is None or a.expected_count is None:
        print("REFUSED input 'input': --files-json and --expected-count are required"); return 1
    try: records = arrays(a.files_json)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"REFUSED input 'input': cannot read files JSON: {exc}"); return 1
    if len(records) != a.expected_count:
        print(f"REFUSED input 'input': record count {len(records)} != expected {a.expected_count}"); return 1
    if len(records) >= 3000: print("REFUSED input 'input': API record cap reached"); return 1
    refused = []
    for record in records:
        if not isinstance(record, dict): refused.append(refusal("unknown", "", "malformed API record")); continue
        status, path, previous = record.get("status", "unknown"), record.get("filename", ""), record.get("previous_filename")
        if status not in STATUSES: refused.append(refusal(status, path, "status is not allowed")); continue
        if unsafe(path): refused.append(refusal(status, path, "filename is not safe")); continue
        if previous is not None and unsafe(previous): refused.append(refusal(status, previous, "previous_filename is not safe")); continue
        if status == "added" and ENTRY_RE.fullmatch(path): continue
        cm = CONFIRM_RE.fullmatch(path)
        if status == "added" and cm and a.author and cm.group(2) == a.author: continue
        if status == "modified" and path == "INDEX.tsv": continue
        if status == "modified" and path == "PUBLIC_REPOS.txt":
            ok, reason = append_only(a.public_repos_base, a.public_repos_head)
            if ok: continue
            refused.append(refusal(status, path, reason)); continue
        refused.append(refusal(status, path, "path is not allowed"))
    if refused: print("\n".join(refused)); return 1
    print("OK"); return 0

if __name__ == "__main__": sys.exit(main())
