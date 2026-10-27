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
    "layer": "raw",
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
    def test_layer_missing_rejected(self):
        self.assert_fails({FACT: entry(FACT, "fact", "concept", drop=("layer",))}, "layer")

    def test_layer_bad_value_rejected(self):
        self.assert_fails({FACT: entry(FACT, "fact", "concept", layer="deep")}, "must be raw, info, critical or law")

    def test_info_without_evidence_rejected(self):
        self.assert_fails({FACT: entry(FACT, "fact", "concept", layer="info")}, "info needs at least 1 evidence id")

    def test_info_with_facts_accepted(self):
        root = self.make({FACT: entry(FACT, "fact", "concept"), HOWTO: entry(HOWTO, "advice", "howto", layer="info", goal="tokens", facts=f"[{FACT}]")})
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 0, out)

    def test_info_with_from_accepted(self):
        root = self.make({FACT: entry(FACT, "fact", "concept"), FACT2: entry(FACT2, "fact", "concept", summary="A database backup restores data after a storage failure", layer="info", **{"from": f"[{FACT}]"})})
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 0, out)

    def test_from_missing_id_rejected(self):
        self.assert_fails({FACT: entry(FACT, "fact", "concept", layer="info", **{"from": "[E-20261026-ffff]"})}, "does not exist")

    def test_facts_self_rejected(self):
        es = good_set(); es[HOWTO] = entry(HOWTO, "advice", "howto", layer="info", goal="tokens", facts=f"[{HOWTO}]")
        self.assert_fails(es, "must not list itself")

    def test_exceptions_on_raw_rejected(self):
        self.assert_fails({FACT: entry(FACT, "fact", "concept", exceptions="Rare cases can make this broad claim fail")}, "not allowed on raw")

    def test_from_self_rejected(self):
        self.assert_fails({FACT: entry(FACT, "fact", "concept", layer="info", **{"from": f"[{FACT}]"})}, "must not list itself")

    def test_critical_needs_two_info_evidence(self):
        es = {FACT: entry(FACT, "fact", "concept", layer="critical", exceptions="Rare cases can make this broad claim fail", **{"from": f"[{FACT2}]"}), FACT2: entry(FACT2, "fact", "concept")}
        self.assert_fails(es, "critical needs at least 2")

    def test_critical_settled_needs_two_confirms(self):
        es = good_set(); es[HOWTO] = entry(HOWTO, "advice", "howto", layer="info", goal="tokens", facts=f"[{FACT}]"); es[CHOICE] = entry(CHOICE, "advice", "choice", layer="info", goal="latency", facts=f"[{DATA}]"); es[FACT] = entry(FACT, "fact", "concept", layer="critical", exceptions="Rare cases can make this broad claim fail", **{"from": f"[{HOWTO}, {CHOICE}]"})
        self.assert_fails(es, "critical entry needs 2 confirms")

    def test_critical_open_accepted(self):
        es = good_set(); es[HOWTO] = entry(HOWTO, "advice", "howto", layer="info", goal="tokens", facts=f"[{FACT}]"); es[CHOICE] = entry(CHOICE, "advice", "choice", layer="info", goal="latency", facts=f"[{DATA}]"); es[FACT] = entry(FACT, "fact", "concept", layer="critical", exceptions="Rare cases can make this broad claim fail", status="open", **{"from": f"[{HOWTO}, {CHOICE}]"})
        code, out = self.run_check(self.make(es), "--write-index")
        self.assertEqual(code, 0, out)

    def test_critical_settled_with_dispute_rejected(self):
        es = good_set(); es[HOWTO] = entry(HOWTO, "advice", "howto", layer="info", goal="tokens", facts=f"[{FACT}]"); es[CHOICE] = entry(CHOICE, "advice", "choice", layer="info", goal="latency", facts=f"[{DATA}]"); es[FACT] = entry(FACT, "fact", "concept", layer="critical", exceptions="Rare cases can make this broad claim fail", **{"from": f"[{HOWTO}, {CHOICE}]"})
        root = self.make(es); p = root / "confirms" / FACT; p.mkdir(parents=True)
        for user in ("bob", "carol"):
            (p / f"{user}-20261026-ab12.md").write_text(confirm(user=user), encoding="utf-8", newline="\n")
        (p / "dave-20261027-cd34.md").write_text(confirm(user="dave", verdict="dispute", repro="run x; got y", date="2026-10-27"), encoding="utf-8", newline="\n")
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 1); self.assertIn("critical entry with a dispute must be open", out)

    def law_set(self, **extra):
        es = good_set()
        es[HOWTO] = entry(HOWTO, "advice", "howto", layer="info", goal="tokens", facts=f"[{DATA}]")
        es[CHOICE] = entry(CHOICE, "advice", "choice", layer="info", goal="latency", facts=f"[{DATA}]")
        es[FACT] = entry(FACT, "fact", "concept", layer="critical",
                          exceptions="Rare cases can make this broad claim fail",
                          status="open", **{"from": f"[{HOWTO}, {CHOICE}]"})
        es[DATA] = entry(DATA, "fact", "data", layer="critical",
                         exceptions="Rare cases can make this broad claim fail",
                         status="open", **{"from": f"[{HOWTO}, {CHOICE}]"})
        es[FIX] = entry(FIX, "fact", "concept", summary="A database backup restores data after a storage failure", layer="law",
                        holds_when="The stated conditions are true for every case",
                        status="open", **{"from": f"[{FACT}, {DATA}]"})
        es.update(extra)
        return es

    def test_critical_without_exceptions_rejected(self):
        self.assert_fails({FACT: entry(FACT, "fact", "concept", layer="critical", **{"from": f"[{FACT2}]"}), FACT2: entry(FACT2, "fact", "concept")}, "critical needs non-empty exceptions")

    def test_law_without_holds_when_rejected(self):
        es = self.law_set(); es[FIX] = entry(FIX, "fact", "concept", layer="law", **{"from": f"[{FACT}, {DATA}]"})
        self.assert_fails(es, "law needs non-empty holds_when")

    def test_holds_when_on_non_law_rejected(self):
        self.assert_fails({FACT: entry(FACT, "fact", "concept", holds_when="The stated conditions are true for every case")}, "only allowed on law")

    def test_law_with_exceptions_rejected(self):
        es = self.law_set(); es[FIX] = entry(FIX, "fact", "concept", layer="law", holds_when="The stated conditions are true for every case", exceptions="Rare cases can make this broad claim fail", **{"from": f"[{FACT}, {DATA}]"})
        self.assert_fails(es, "not allowed on law")

    def test_law_needs_two_critical_evidence(self):
        es = self.law_set(); es[FIX] = entry(FIX, "fact", "concept", layer="law", holds_when="The stated conditions are true for every case", **{"from": f"[{HOWTO}, {CHOICE}]"})
        self.assert_fails(es, "law needs at least 2 evidence")

    def test_law_settled_needs_three_confirms_two_envs(self):
        es = self.law_set(); es[FIX] = entry(FIX, "fact", "concept", layer="law", holds_when="The stated conditions are true for every case", status="settled", **{"from": f"[{FACT}, {DATA}]"})
        root = self.make(es); p = root / "confirms" / FIX; p.mkdir(parents=True)
        for user, env in (("bob", "linux"), ("carol", "linux")):
            (p / f"{user}-20261026-ab12.md").write_text(confirm(entry_id=FIX, user=user, env=f"[{env}]") , encoding="utf-8", newline="\n")
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 1); self.assertIn("law entry needs 3 confirms", out)

    def test_law_settled_with_dispute_rejected(self):
        es = self.law_set(); es[FIX] = entry(FIX, "fact", "concept", layer="law", holds_when="The stated conditions are true for every case", status="settled", **{"from": f"[{FACT}, {DATA}]"})
        root = self.make(es); p = root / "confirms" / FIX; p.mkdir(parents=True)
        for user, env in (("bob", "linux"), ("carol", "windows"), ("dave", "linux")):
            (p / f"{user}-20261026-ab12.md").write_text(confirm(entry_id=FIX, user=user, env=f"[{env}]"), encoding="utf-8", newline="\n")
        (p / "dave-20261027-cd34.md").write_text(confirm(entry_id=FIX, user="dave", env="[linux]", verdict="dispute", repro="run x; got y", date="2026-10-27"), encoding="utf-8", newline="\n")
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 1); self.assertIn("a law with a dispute must be open", out)

    def test_law_open_accepted(self):
        es = self.law_set(); self.assertEqual(self.run_check(self.make(es), "--write-index")[0], 0)
        self.assertEqual(self.run_check(self.make(es), "--write-index")[0], 0)

    def test_raw_measured_settled_rejected(self):
        self.assert_fails({FACT: entry(FACT, "fact", "concept", origin="measured")}, "raw measured entry needs 1 confirm")

    def test_raw_measured_settled_with_confirm_accepted(self):
        root = self.make({FACT: entry(FACT, "fact", "concept", origin="measured", repro="run the check")})
        self.add_confirm = root / "confirms" / FACT / "bob-20261026-ab12.md"; self.add_confirm.parent.mkdir(parents=True); self.add_confirm.write_text(confirm(), encoding="utf-8", newline="\n")
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 0, out)

    def test_raw_measured_settled_with_dispute_rejected(self):
        root = self.make({FACT: entry(FACT, "fact", "concept", origin="measured", repro="run the check")})
        p = root / "confirms" / FACT; p.mkdir(parents=True)
        (p / "bob-20261026-ab12.md").write_text(confirm(), encoding="utf-8", newline="\n")
        (p / "carol-20261027-cd34.md").write_text(confirm(user="carol", verdict="dispute", repro="run x; got y", date="2026-10-27"), encoding="utf-8", newline="\n")
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 1); self.assertIn("raw measured entry with a dispute must be open", out)

    def test_raw_quoted_settled_accepted(self):
        root = self.make({FACT: entry(FACT, "fact", "concept", origin="quoted", source="https://example.com")})
        self.assertEqual(self.run_check(root, "--write-index")[0], 0)
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


class TestDuplicates(Base):
    def pair(self, second_summary, **extra):
        return {
            FACT: entry(FACT, "fact", "concept"),
            FACT2: entry(FACT2, "fact", "concept", summary=second_summary, **extra),
        }

    def test_identical_summary_rejected(self):
        self.assert_fails(self.pair(SUMMARIES["concept"]), "near-duplicate of")

    def test_supersedes_link_accepts_duplicate(self):
        root = self.make(self.pair(SUMMARIES["concept"], supersedes=f"[{FACT}]"))
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 0, out)

    def test_contradicts_link_accepts_duplicate(self):
        root = self.make(self.pair(SUMMARIES["concept"], contradicts=f"[{FACT}]"))
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 0, out)

    def test_clearly_different_summaries_accepted(self):
        root = self.make(self.pair("A database backup restores data after a storage failure"))
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 0, out)

    def test_supersedes_missing_rejected(self):
        self.assert_fails(self.one(entry(FACT, "fact", "concept", supersedes="[E-20261026-ffff]")),
                          "E-20261026-ffff does not exist")

    def test_supersedes_self_rejected(self):
        self.assert_fails(self.one(entry(FACT, "fact", "concept", supersedes=f"[{FACT}]")),
                          "must not list itself")

    def test_similar_prints_pair_and_exits_zero(self):
        root = self.make(self.pair(SUMMARIES["concept"]))
        code, out = self.run_check(root, "--similar", "0.6")
        self.assertEqual(code, 0, out)
        self.assertIn(f"\t{FACT}\t{FACT2}\t", out)


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

    def test_long_hex(self):
        tok = "0123456789abcdef" * 3
        self.priv("Authorization: " + tok, tok)

    def test_long_mixed_token(self):
        tok = "Ab3" * 15
        self.priv("key " + tok, tok)

    def test_unlisted_repo_link(self):
        out = self.assert_fails({FACT: entry(FACT, "fact", "concept",
                                body="See https://github.com/acme/internal-tools now")},
                                "not in PUBLIC_REPOS.txt")
        self.assertNotIn("acme", out)

    def test_listed_repo_link_allowed(self):
        root = self.make({FACT: entry(FACT, "fact", "concept",
                                      body="See https://github.com/acme/tools.git now")})
        with open(root / "PUBLIC_REPOS.txt", "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# public\nAcme/Tools\n")
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 0, out)

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
        self.assertEqual(rows[0], "id\tforce\tkind\tlayer\tdomain\ttags\tsummary\tconfirms\tdisputes\tlast_checked")
        ids = [r.split("\t")[0] for r in rows[1:]]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), 6)

    def test_index_has_layer_column(self):
        root = self.make(good_set()); self.run_check(root, "--write-index")
        self.assertEqual((root / "INDEX.tsv").read_text(encoding="utf-8").splitlines()[0].split("\t")[3], "layer")


def confirm(entry_id=FACT, verdict="confirm", user="bob", date="2026-10-26",
            env="[linux]", repro=None, by=None, body="Ran it; same result."):
    lines = ["---", f"entry: {entry_id}", f"verdict: {verdict}",
             f"by: {by or 'gh:' + user}", f"checked_at: {date}", f"env: {env}"]
    if repro: lines.append(f"repro: {repro}")
    return "\n".join(lines + ["---", body, ""])


class TestConfirms(Base):
    def add(self, root, files):
        for rel, text in files.items():
            p = root / "confirms" / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)

    def row(self, root, entry_id=FACT):
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 0, out)
        for r in (root / "INDEX.tsv").read_text(encoding="utf-8").splitlines():
            if r.startswith(entry_id + "\t"):
                return r.split("\t")[-3:]

    def fails(self, files, needle):
        root = self.make(good_set())
        self.add(root, files)
        code, out = self.run_check(root, "--write-index")
        self.assertEqual(code, 1, out)
        self.assertIn(needle, out)

    def test_valid_confirm_counted(self):
        root = self.make(good_set())
        self.add(root, {f"{FACT}/bob-20261026-ab12.md": confirm()})
        self.assertEqual(self.row(root), ["1", "0", "2026-10-26"])

    def test_no_confirms_defaults(self):
        self.assertEqual(self.row(self.make(good_set())), ["0", "0", "2026-10-26"])

    def test_self_confirm_not_counted(self):
        root = self.make(good_set())
        self.add(root, {f"{FACT}/alice-20261026-ab12.md": confirm(user="alice")})
        self.assertEqual(self.row(root)[:2], ["0", "0"])

    def test_one_user_counts_once_newest_wins(self):
        root = self.make(good_set())
        self.add(root, {
            f"{FACT}/bob-20261026-ab12.md": confirm(),
            f"{FACT}/bob-20261026-cd34.md": confirm(),
        })
        self.assertEqual(self.row(root)[:2], ["1", "0"])
        self.add(root, {f"{FACT}/bob-20261027-ef56.md":
                        confirm(verdict="dispute", date="2026-10-27", repro="run x; got y")})
        self.assertEqual(self.row(root), ["0", "1", "2026-10-27"])

    def test_dispute_without_repro_rejected(self):
        self.fails({f"{FACT}/bob-20261026-ab12.md": confirm(verdict="dispute")}, "repro")

    def test_unknown_key_rejected(self):
        self.fails({f"{FACT}/bob-20261026-ab12.md":
                    confirm().replace("env:", "note: x\nenv:")}, "unknown key note")

    def test_missing_entry_rejected(self):
        gone = "E-20261026-ffff"
        self.fails({f"{gone}/bob-20261026-ab12.md": confirm(entry_id=gone)}, "does not exist")

    def test_folder_entry_mismatch_rejected(self):
        self.fails({f"{FACT}/bob-20261026-ab12.md": confirm(entry_id=DATA)}, "folder name")

    def test_by_file_name_mismatch_rejected(self):
        self.fails({f"{FACT}/bob-20261026-ab12.md": confirm(by="gh:carol")}, "gh:bob")

    def test_future_date_rejected(self):
        self.fails({f"{FACT}/bob-29991231-ab12.md": confirm(date="2999-12-31")}, "future")


if __name__ == "__main__":
    unittest.main()
