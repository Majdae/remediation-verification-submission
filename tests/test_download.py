"""Offline regression suite. Run: python3 -m unittest discover -s tests -v
Set DOWNLOAD_IMPL=<path to .py> to test another implementation (e.g. evidence/download_original.py)."""
import importlib.util, json, os, pathlib, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMPL = pathlib.Path(os.environ.get("DOWNLOAD_IMPL", ROOT / "inputs" / "download.py"))
spec = importlib.util.spec_from_file_location("impl", IMPL)
impl = importlib.util.module_from_spec(spec); spec.loader.exec_module(impl)
FILES = json.loads((ROOT / "inputs" / "files.json").read_text(encoding="utf-8"))
FORBIDDEN = ["blue forecast", "red forecast", "red-old", "DEMO_NONFUNCTIONAL", "operator notes", "restricted"]


def dl(tenant, path):
    return impl.download({"request_id": "t", "tenant": tenant, "path": path}, FILES)


class DownloadTests(unittest.TestCase):
    def ok(self, tenant, path, body):
        r = dl(tenant, path); self.assertEqual(r["status"], 200); self.assertEqual(r["body"], body)

    def denied(self, tenant, path):
        r = dl(tenant, path)
        self.assertEqual(r["status"], 403, r)
        for s in FORBIDDEN:
            self.assertNotIn(s, r["body"])

    def test_01_red_normal(self): self.ok("red", "exports/red/q1.csv", "red forecast,120")
    def test_02_blue_normal(self): self.ok("blue", "exports/blue/q2.csv", "blue forecast,340")
    def test_03_encoded_space(self): self.ok("red", "exports/red/quarter%201.csv", "red encoded-name forecast,125")
    def test_04_encoded_slash_hex_case_equivalent(self):
        self.ok("red", "exports/red%2fq1.csv", "red forecast,120")
        self.ok("red", "exports/red%2Fq1.csv", "red forecast,120")
    def test_05_dot_segment_inside_root(self): self.ok("red", "exports/red/./q1.csv", "red forecast,120")
    def test_06_sibling_prefix(self): self.denied("red", "exports/red-old/staging.txt")
    def test_07_encoded_traversal_other_tenant(self): self.denied("red", "exports/red/%2e%2e/blue/q2.csv")
    def test_08_encoded_traversal_uppercase_private(self): self.denied("red", "exports/red/%2E%2E/%2E%2E/private/operator.txt")
    def test_09_encoded_slash_traversal(self): self.denied("blue", "exports/blue%2f..%2fred/q1.csv")
    def test_10_plain_traversal(self): self.denied("red", "exports/red/../../private/operator.txt")
    def test_11_other_tenant_path(self): self.denied("red", "exports/blue/q2.csv")
    def test_12_private(self): self.denied("blue", "private/operator.txt")
    def test_13_missing_allowed_file(self):
        r = dl("red", "exports/red/nope.csv"); self.assertEqual((r["status"], r["body"]), (404, "Missing"))
    def test_14_unknown_tenant(self): self.denied("green", "exports/green/x.csv")
    def test_15_absolute_path(self): self.denied("red", "/exports/red/q1.csv")
    def test_16_encoded_absolute_path(self): self.denied("red", "%2fexports/red/q1.csv")
    def test_17_literal_backslash(self): self.denied("red", "exports\\red\\q1.csv")
    def test_18_encoded_backslash(self): self.denied("red", "exports/red/%5cq1.csv")
    def test_19_denial_independent_of_outside_existence(self):
        a = dl("red", "exports/red-old/staging.txt"); b = dl("red", "exports/red-old/does-not-exist.txt")
        self.assertEqual((a["status"], a["body"]), (b["status"], b["body"]))
    def test_20_double_encoding_decoded_once(self):
        r = dl("red", "exports/red/quarter%2520 1.csv"); self.assertEqual(r["status"], 404)
    def test_22_double_encoded_name_not_decoded_twice(self):
        # %2520 -> %20 (literal), NOT a space; "quarter%201.csv" is not a file, so 404 rather than 200.
        r = dl("red", "exports/red/quarter%25201.csv"); self.assertEqual((r["status"], r["body"]), (404, "Missing"))
    def test_23_double_encoded_traversal_stays_in_root(self):
        # decoded once -> literal "%2e%2e" directory name inside red: in-root missing, not traversal/denial.
        r = dl("red", "exports/red/%252e%252e/blue/q2.csv")
        self.assertEqual((r["status"], r["body"]), (404, "Missing"))
    def test_21_bare_root_denied(self):
        self.denied("red", "exports/red"); self.denied("red", "exports/red/")


if __name__ == "__main__":
    unittest.main()
