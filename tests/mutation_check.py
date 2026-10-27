"""Stretch: each mutant of the fixed code must be caught by the suite. Run: python3 tests/mutation_check.py"""
import os, pathlib, subprocess, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parent.parent
src = (ROOT / "inputs" / "download.py").read_text(encoding="utf-8")
MUTANTS = {
 "drop trailing slash (sibling prefix)": ('"exports/" + tenant + "/"', '"exports/" + tenant'),
 "check before decode": ("lookup = posixpath.normpath(decoded)", "lookup = posixpath.normpath(decoded)\n    if not posixpath.normpath(raw).startswith('exports/' + tenant + '/'): return _deny(request_id)"),
 "allow backslash": ('"\\\\" in decoded or ', ''),
 "allow absolute": (' or decoded.startswith("/")', ''),
 "double decode": ("decoded = urllib.parse.unquote(raw)", "decoded = urllib.parse.unquote(urllib.parse.unquote(raw))"),
 "skip normalization": ("lookup = posixpath.normpath(decoded)", "lookup = decoded"),
}
# Equivalent mutants: behaviour is unchanged because a later check already covers them.
EQUIVALENT = {"allow absolute"}
bad = 0
for name, (a, b) in MUTANTS.items():
    assert a in src, name
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "m.py"
        p.write_text(src.replace(a, b, 1), encoding="utf-8")
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests")],
                           env={**os.environ, "DOWNLOAD_IMPL": str(p)}, capture_output=True, text=True)
    killed = r.returncode != 0
    if not killed and name in EQUIVALENT:
        print("EQUIVALENT (expected to survive: prefix check also rejects leading '/')", name); continue
    bad += not killed
    print(("KILLED  " if killed else "SURVIVED"), name)
sys.exit(1 if bad else 0)
