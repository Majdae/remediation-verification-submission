# Remediation verification: ArchiveKit download path boundary

Environment: re-run on Windows (PowerShell), Python 3.14.3, standard library only (see evidence/versions.txt).
The saved evidence files were captured earlier on Linux / Python 3.12.3; results are identical on both.
Commands (from the candidate/ folder):
  python -m unittest discover -s tests -v          # fixed code: 23 tests OK
  $env:DOWNLOAD_IMPL="evidence/download_original.py"; python -m unittest discover -s tests   # original: 7 failures expected
  python tests/mutation_check.py                   # stretch: 5 killed, 1 equivalent
(On Linux/macOS: sh run_all.sh, python3 instead of python.)

## 1. Verdict on the teammate's claim: "fixed" is **false**
The original (`evidence/download_original.py`, unchanged) checks the path **before** decoding and looks up the path **after** decoding.
That is exactly the C2 trap. It also uses `startswith("exports/red")` with no trailing slash, so `red-old` counts as red.

Replay: `python evidence/download_original.py evidence/probes.json` (output saved in `evidence/original_probe_output.json`).

| Probe (tenant red unless noted) | Path | Contract | Original | Repaired |
|---|---|---|---|---|
| control: normal | `exports/red/q1.csv` | 200 | 200 | 200 |
| control: normal (blue) | `exports/blue/q2.csv` | 200 | 200 | 200 |
| control: encoded space | `exports/red/quarter%201.csv` | 200 | 200 | 200 |
| control: dot segment in root | `exports/red/./q1.csv` | 200 | 200 | 200 |
| control: missing in root | `exports/red/nope.csv` | 404 | 404 | 404 |
| **sibling prefix** | `exports/red-old/staging.txt` | 403 | **200, leaks staging token** | 403 |
| **encoded traversal, other tenant** | `exports/red/%2e%2e/blue/q2.csv` | 403 | **200, leaks blue data** | 403 |
| **encoded traversal, private/** | `exports/red/%2E%2E/%2E%2E/private/operator.txt` | 403 | **200, leaks operator notes** | 403 |
| **encoded slash traversal** (tenant blue) | `exports/blue%2f..%2fred/q1.csv` | 403 | **200, leaks red data** | 403 |
| encoded backslash | `exports/red/%5cq1.csv` | 403 | 404 (wrong code, no leak) | 403 |
| sibling, nonexistent file | `exports/red-old/none.txt` | 403 (C4: independent of existence) | 404 (wrong) | 403 |
| other tenant, plain | `exports/blue/q2.csv` | 403 | 403 | 403 |
| absolute / unknown tenant | `/exports/red/q1.csv`; tenant `green` | 403 | 403 | 403 |
| double-encoded space | `exports/red/quarter%2520 1.csv` | 404 (decode once) | 404 | 404 |

**Why the smoke test was insufficient:** `requests.json` has only three well-formed in-root downloads. They never contain a `%`-encoded dot/slash,
a sibling directory, or a path that is wrong only after decoding, so they pass no matter where the boundary check sits relative to decoding.
A passing happy path says nothing about the boundary.

## 2. Repair (`inputs/download.py`; `files.json` and contract unchanged)
Decode once, reject backslash/NUL/leading `/` on the **decoded** value, `posixpath.normpath` once, then require `startswith("exports/<tenant>/")`
(trailing slash: strictly inside, excludes `red-old` and the bare root). The string that is checked is the string that is looked up.
This is a boundary fix, not deny-everything: tests 01-05, 13, 20, 22, 23 prove legitimate downloads, encoded names, in-root dot segments and
in-root 404s still work.

## 3. Regression suite (`tests/test_download.py`, 23 cases, real `download()` responses)
Each test asserts status **and** body (exact content for 200/404; no forbidden strings for 403).
- Fixed code: `Ran 23 tests ... OK` (`evidence/tests_on_fixed.txt`).
- Original: `FAILED (failures=7)` (`evidence/tests_on_original.txt`): tests 06, 07, 08, 09, 18, 19, 21. All 7 are real defects; the 16 others pass on both, which shows the suite does not just deny everything.
- Stretch: `tests/mutation_check.py` mutates the fixed code 6 ways; 5 are killed. The one survivor ("allow absolute") is an *equivalent* mutant, since the prefix check also rejects a leading `/`; it is declared in the script.

## 4. Release recommendation: **ready in this model** (with limits)
All contract rules C1-C5 hold for the fixture; original leaks are closed; valid downloads work; mutation check is clean.
Limitations: this proves string-level path handling on an in-memory map only. It does **not** prove real-filesystem safety: symlinks,
case-insensitive or Unicode-normalising filesystems, Windows drives, HTTP-layer parsing (`?`, `#`, `;`, double-decode by a proxy), or
non-fixture tenants. NUL and non-UTF-8 escapes are handled defensively but are outside the stated contract.
**Next integration check:** run the same probe list through the real HTTP stack in a throwaway tenant tree with a planted symlink and
case-variant directory, confirming the production lookup resolves (e.g. `realpath`) to a location inside the tenant root and that decoding happens once across proxy + app.

## 5. Walkthrough (text)
1. The three commands at the top of this file show: fixed = 23 tests OK, original = 7 failures, mutation = 5 killed + 1 equivalent. 2. `evidence/original_probe_output.json` shows four 200 responses that leak other data.
3. `inputs/download.py` is the repair; the diff against `evidence/download_original.py` is ~12 lines. 4. Limits above.

## 6. Decision / work log
- Prioritisation: confirm the leaks first (cheapest proof that the claim is false), then repair, then regression tests, then the mutation check as a stretch.
- Obstacle: my first test run on Windows failed with "Start directory is not importable: 'tests'". The cause was the working directory: the archive has a candidate/ subfolder that contains tests/ and evidence/. Response: cd into candidate/ and re-run.
- Validation: I re-ran everything on Windows (Python 3.14.3): 23 tests pass on the repaired code, 7 fail on the original, mutation check gives 5 killed and 1 equivalent. Results match the saved evidence.
- Limits / next step: see section 4.

## 7. AI-use note
I wrote the first version of this submission myself: the repair in inputs/download.py, the 23 tests, the probes and the mutation check. I then used Claude (Anthropic) in a chat to understand the vulnerability better and to review and improve my work: it explained why an encoded %2e%2e passes the original check, and it reviewed my documentation and my Windows commands.
Corrected output: Claude suggested building the zip with Compress-Archive. When the archive was inspected, its paths used backslashes (Windows style), which can break extraction on Linux and macOS. I rebuilt it with the Python zipfile module (forward slashes) and listed the names again to confirm.
I re-ran the commands listed at the top on Windows (Python 3.14.3); the files in evidence/ were captured earlier and the Windows results are identical.
