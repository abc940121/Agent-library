import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECKER = Path(__file__).resolve().parent / "check_entries.py"

FACT = "E-20261026-0001".replace("0001", "a001")
FACT2 = "E-20261026-a002"
DATA = "E-20261026-a003"
HOWTO = "E-20261026-b001"
FIX = "E-20261026-b002"
CHOICE = "E-20261026-b003"
POLICY = "E-20261026-c001"

BASE = {
    "origin": "guess", "domain": "[n8n]", "tags": "[]", "negative": "no",
    "status": "settled", "checked_at": "2026-10-26", "added_by": "gh:alice",
}

SUMMARIES = {
    "concept": "A webhook node waits for an outside HTTP request to start a run",
    "data": "Qwen3 8B answered 12 of 20 test prompts correctly in our run",
    "howto": "To keep prompts short, send only the node names to the model",
    "fix": "When the webhook returns an error, check that the workflow is active",
    "choice": "For short prompts, pick a small model over a large one because it is faster",
    "policy": "In shared scopes, owners must review every change before merge",
}


def entry(id_, force, kind, summary=None, body="Some body text.", drop=(), **extra):
    f = dict(BASE)
    f.update({"id": id_, "force": force, "kind": kind,
              "summary": summary or SUMMARIES[kind]})
    f.update(extra)
    for k in drop:
        f.pop(k, None)
    lines = ["---"] + [f"{k}: {v}" for k, v in f.items()] + ["---", body, ""]
    return "\n".join(lines)


def good_set():
    return {
        FACT: entry(FACT, "fact", "concept"),
        DATA: entry(DATA, "fact", "data"),
        HOWTO: entry(HOWTO, "advice", "howto", goal="tokens", facts=f"[{FACT}]"),
        FIX: entry(FIX, "advice", "fix", goal="symptom"),
        CHOICE: entry(CHOICE, "advice", "choice", goal="latency", facts=f"[{DATA}]"),
        POLICY: entry(POLICY, "rule", "policy", rule_scope="shared",
                      owner="gh:alice"),
    }


class Base(unittest.TestCase):
    def make(self, entries, scopes="scope\towners\nshared\tgh:alice gh:bob\n"):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        (root / "entries").mkdir()
        for id_, text in entries.items():
            with open(root / "entries" / f"{id_}.md", "w", encoding="utf-8",
                      newline="\n") as fh:
                fh.write(text)
        with open(root / "SCOPES.tsv", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(scopes)
        return root

    def run_check(self, root, *args):
        p = subprocess.run(
            [sys.executable, "-X", "utf8", str(CHECKER), "--root", str(root), *args],
            capture_output=True, text=True, encoding="utf-8")
        return p.returncode, p.stdout

    def assert_fails(self, entries, needle, **kw):
        root = self.make(entries, **kw)
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 1, out)
        self.assertIn(needle, out)
        return out

    def one(self, text, id_=FACT, **kw):
        return {id_: text}


class TestValid(Base):
    def test_all_valid_kinds_ok(self):
        root = self.make(good_set())
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 0, out)
        self.assertIn("OK 6 entries", out)
        code, out = self.run_check(root)
        self.assertEqual(code, 0, out)

    def test_number_stripping(self):
        s = "Qwen3 8B is slower on n8n 2.x"
        root = self.make({FACT: entry(FACT, "fact", "concept", summary=s + " than others")})
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 0, out)

    def test_concept_with_number_fails(self):
        self.assert_fails({FACT: entry(FACT, "fact", "concept",
                          summary="The webhook node waits for 30 seconds before a timeout")},
                          "concept summary")


class TestFields(Base):
    def test_missing_required_field(self):
        self.assert_fails({FACT: entry(FACT, "fact", "concept", drop=("status",))},
                          "status")

    def test_force_kind_mismatch(self):
        self.assert_fails({FACT: entry(FACT, "fact", "howto")}, "kind")

    def test_unknown_key(self):
        self.assert_fails({FACT: entry(FACT, "fact", "concept", colour="red")},
                          "unknown key colour")

    def test_id_mismatch(self):
        self.assert_fails({FACT: entry(FACT2, "fact", "concept")}, "does not match")

    def test_contradicts_missing(self):
        self.assert_fails({FACT: entry(FACT, "fact", "concept",
                                       contradicts="[E-20261026-ffff]")},
                          "E-20261026-ffff does not exist")

    def test_facts_missing_and_not_fact(self):
        es = good_set()
        es[HOWTO] = entry(HOWTO, "advice", "howto", goal="tokens",
                          facts="[E-20261026-ffff]")
        self.assert_fails(es, "E-20261026-ffff does not exist")
        es[HOWTO] = entry(HOWTO, "advice", "howto", goal="tokens", facts=f"[{FIX}]")
        self.assert_fails(es, "is not a fact")

    def test_howto_without_facts(self):
        es = good_set()
        es[HOWTO] = entry(HOWTO, "advice", "howto", goal="tokens")
        self.assert_fails(es, "needs at least one fact")

    def test_bad_goal(self):
        es = good_set()
        es[HOWTO] = entry(HOWTO, "advice", "howto", goal="speed", facts=f"[{FACT}]")
        self.assert_fails(es, "goal")

    def test_symptom_goal_only_for_fix(self):
        es = good_set()
        es[HOWTO] = entry(HOWTO, "advice", "howto", goal="symptom", facts=f"[{FACT}]")
        self.assert_fails(es, "goal symptom is not one of the allowed goals")

    def test_rule_unregistered_scope_and_owner(self):
        es = good_set()
        es[POLICY] = entry(POLICY, "rule", "policy", rule_scope="nope", owner="gh:alice")
        self.assert_fails(es, "not in SCOPES.tsv")
        es[POLICY] = entry(POLICY, "rule", "policy", rule_scope="shared", owner="gh:eve")
        self.assert_fails(es, "not listed")

    def test_origin_requirements(self):
        self.assert_fails({FACT: entry(FACT, "fact", "concept", origin="measured")},
                          "repro")
        self.assert_fails({FACT: entry(FACT, "fact", "concept", origin="quoted",
                                       source="http://x.org")}, "source")


class TestTemplates(Base):
    def bad(self, force, kind, summary, **extra):
        es = good_set()
        es[FACT] = entry(FACT, force, kind, summary=summary, **extra)
        out = self.assert_fails(es, "summary")
        self.assertIn(FACT, out)

    def test_data_without_number(self):
        self.bad("fact", "data", "Webhook nodes are slower than the manual trigger node")

    def test_imperative_concept(self):
        self.bad("fact", "concept", "Use the webhook node to receive outside HTTP calls")

    def test_howto_template(self):
        self.bad("advice", "howto", "Send only node names to the model to save tokens",
                 goal="tokens", facts=f"[{DATA}]")

    def test_fix_template(self):
        self.bad("advice", "fix", "When the webhook is slow, check that the workflow is active",
                 goal="latency")

    def test_choice_template(self):
        self.bad("advice", "choice", "For short prompts, pick a small model, it is faster",
                 goal="latency", facts=f"[{DATA}]")

    def test_policy_template(self):
        self.bad("rule", "policy", "In shared scopes, owners review every change before merge",
                 rule_scope="shared", owner="gh:alice")


class TestPrivacy(Base):
    def priv(self, line, secret):
        out = self.assert_fails({FACT: entry(FACT, "fact", "concept",
                                             body="Line one.\n" + line)}, "privacy")
        self.assertIn(":", out)
        self.assertNotIn(secret, out)

    def test_drive_path(self):
        self.priv("See C:\\Users\\someone\\notes.txt for more", "someone")

    def test_private_ip(self):
        self.priv("The server is at 192.168.1.44 today", "192.168.1.44")

    def test_token(self):
        tok = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2"
        self.priv("token " + tok, tok)

    def test_localhost_allowed(self):
        root = self.make({FACT: entry(FACT, "fact", "concept",
                                      body="Listens on 127.0.0.1 and 0.0.0.0")})
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 0, out)


class TestIndex(Base):
    def test_stale_index(self):
        root = self.make(good_set())
        self.assertEqual(self.run_check(root, "--write-index")[0], 0)
        p = root / "entries" / f"{DATA}.md"
        p.write_text(p.read_text(encoding="utf-8").replace("12 of 20", "13 of 20"),
                     encoding="utf-8", newline="\n")
        code, out = self.run_check(root)
        self.assertEqual(code, 1)
        self.assertIn("--write-index", out)

    def test_missing_index(self):
        root = self.make(good_set())
        code, out = self.run_check(root)
        self.assertEqual(code, 1)
        self.assertIn("--write-index", out)

    def test_index_content_sorted(self):
        root = self.make(good_set())
        self.run_check(root, "--write-index")
        rows = (root / "INDEX.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(rows[0], "id\tforce\tkind\tdomain\ttags\tsummary")
        ids = [r.split("\t")[0] for r in rows[1:]]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), 6)


if __name__ == "__main__":
    unittest.main()
