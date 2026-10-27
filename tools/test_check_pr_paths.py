import json, subprocess, sys, tempfile, unittest
from pathlib import Path

CHECKER = Path(__file__).with_name("check_pr_paths.py")

class TestPaths(unittest.TestCase):
    def run_check(self, records, expected=None, **kw):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "files.json"
            f.write_text(kw.pop("json_text", json.dumps(records)), encoding="utf-8")
            args = [sys.executable, str(CHECKER), "--files-json", str(f),
                    "--expected-count", str(len(records) if expected is None else expected)]
            for key, value in kw.items(): args += ["--" + key.replace("_", "-"), str(value)]
            return subprocess.run(args, capture_output=True, text=True)

    def test_allowed_and_legacy_rejections(self):
        self.assertEqual(self.run_check([{"status":"added","filename":"entries/E-20261027-ab12.md"}]).returncode, 0)
        for status in ("modified", "removed", "renamed"):
            self.assertEqual(self.run_check([{ "status": status, "filename":"entries/E-20261027-ab12.md"}]).returncode, 1)
        self.assertEqual(self.run_check([{ "status":"modified", "filename":"INDEX.tsv"}]).returncode, 0)
        # non-ASCII digits (Arabic-Indic) must not match the date part
        self.assertEqual(self.run_check([{"status":"added","filename":"entries/E-٢٠٢٦١٠٢٧-ab12.md"}]).returncode, 1)

    def test_unsupported_statuses_and_unsafe_names(self):
        for status in ("copied", "changed", "unchanged", "unknown"):
            self.assertEqual(self.run_check([{ "status":status, "filename":"x"}]).returncode, 1)
        for name in ("entries/E-20261027-ab12.md\n", "x\r", "x\t", "x..y", "x "):
            self.assertEqual(self.run_check([{ "status":"added", "filename":name}]).returncode, 1)

    def test_counts_and_concatenated_arrays(self):
        self.assertEqual(self.run_check([{ "status":"added", "filename":"entries/E-20261027-ab12.md"}], expected=2).returncode, 1)
        records = [{"status":"added", "filename":f"entries/E-20261027-{i:04x}.md"} for i in range(3000)]
        self.assertEqual(self.run_check(records).returncode, 1)
        self.assertEqual(self.run_check([{"status":"added","filename":"entries/E-20261027-ab12.md"}], json_text='[{"status":"added","filename":"entries/E-20261027-ab12.md"}][]').returncode, 0)

    def test_public_repos_append_only(self):
        with tempfile.TemporaryDirectory() as td:
            base, head = Path(td)/"base", Path(td)/"head"
            base.write_bytes(b"one\ntwo\n")
            for content, code in ((b"one\ntwo\nthree\n", 0), (b"zero\none\ntwo\n", 1), (b"one\nthree\ntwo\n", 1), (b"one\ntwo\n", 1), (b"one\ntwo\n---\n+++\n", 0)):
                head.write_bytes(content)
                self.assertEqual(self.run_check([{"status":"modified","filename":"PUBLIC_REPOS.txt"}], public_repos_base=base, public_repos_head=head).returncode, code)
            base.write_bytes(b"one")
            head.write_bytes(b"one\ntwo\n")
            self.assertEqual(self.run_check([{"status":"modified","filename":"PUBLIC_REPOS.txt"}], public_repos_base=base, public_repos_head=head).returncode, 0)
            self.assertEqual(self.run_check([{"status":"modified","filename":"PUBLIC_REPOS.txt"}], public_repos_base=base).returncode, 1)

    def test_confirm_paths(self):
        own = [{"status":"added","filename":"confirms/E-20261027-ab12/bob-20261027-cd34.md"}]
        self.assertEqual(self.run_check(own, author="bob").returncode, 0)
        self.assertEqual(self.run_check(own, author="mallory").returncode, 1)
        self.assertEqual(self.run_check(own).returncode, 1)
        self.assertEqual(self.run_check([dict(own[0], status="modified")], author="bob").returncode, 1)
        self.assertEqual(self.run_check([{"status":"added","filename":"confirms/E-20261027-ab12/bob-x.md"}], author="bob").returncode, 1)

    def test_confirm_with_its_entry_refused(self):
        records = [{"status":"added","filename":"entries/E-20261027-ab12.md"},
                   {"status":"added","filename":"confirms/E-20261027-ab12/bob-20261027-cd34.md"}]
        r = self.run_check(records, author="bob")
        self.assertEqual(r.returncode, 1); self.assertIn("later PR", r.stdout)

    def test_maintainer(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td)/"f"; f.write_text("[]", encoding="utf-8")
            self.assertEqual(subprocess.run([sys.executable, str(CHECKER), "--maintainer", "--files-json", str(f), "--expected-count", "0"]).returncode, 0)

if __name__ == "__main__": unittest.main()
