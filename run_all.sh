#!/bin/sh
# One command, offline, stdlib only. Run from candidate/:  sh run_all.sh
set -e
cd "$(dirname "$0")"
echo "### Fixed implementation"; python3 -m unittest discover -s tests
echo "### Original implementation (failures EXPECTED)"; DOWNLOAD_IMPL=evidence/download_original.py python3 -m unittest discover -s tests || true
echo "### Mutation check"; python3 tests/mutation_check.py
