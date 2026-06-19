#!/usr/bin/env bash
# verify.sh — build the binding, run every contract case through bw_cpp,
# and assert parity via the contract's own compare.py.
#
# Identical proof methodology to hallmodel-core/proof/verify.sh, but the
# kernel is reached through the pybind11 binding rather than driven directly
# from C++. A green run here means: (a) the pinned hallmodel-core submodule
# still passes parity, and (b) the binding does not introduce any drift.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
CORE="$REPO_ROOT/external/hallmodel-core"
OUT_DIR="$SCRIPT_DIR/outputs"
LOG="$SCRIPT_DIR/last_run.log"
VENV="$REPO_ROOT/build/.verify-venv"

# Use an ephemeral venv so the proof is reproducible regardless of the
# caller's Python environment (handles PEP 668 externally-managed Pythons).
if [[ ! -d "$VENV" ]]; then
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet --upgrade pip pybind11 numpy
fi
PY="$VENV/bin/python3"
PIP="$VENV/bin/pip"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

{
  echo "----- hallmodel-py parity verification -----"
  echo "date:          $(date -u +%FT%TZ)"
  echo "host:          $(uname -srm)"
  echo "python:        $($PY --version)"
  echo "core submodule sha: $(git -C "$CORE" rev-parse HEAD)"
  echo "repo:          $REPO_ROOT"
  echo

  if [[ ! -e "$CORE/contract/cases.json" ]]; then
    echo "ERROR: submodule not initialized; run: git submodule update --init --recursive" >&2
    exit 2
  fi

  echo "----- installing bw_cpp -----"
  "$PIP" install -e "$REPO_ROOT" --quiet

  echo
  echo "----- driving cases through bw_cpp -----"
  "$PY" - "$CORE/contract/cases.json" "$OUT_DIR" <<'PY'
import json
import sys
from pathlib import Path
import numpy as np
import bw_cpp

cases_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])

def arr(x):
    return x.tolist() if isinstance(x, np.ndarray) else x

def serialize(result):
    return {k: arr(v) for k, v in result.items()}

def run_case(case):
    fn = case["fn"]; a = case["args"]
    if fn == "adult_weight":
        return serialize(bw_cpp.adult_weight(**a))
    if fn == "child_weight":
        return serialize(bw_cpp.child_weight(**a))
    if fn == "EnergyBuilder":
        res = bw_cpp.EnergyBuilder().build(a["energy"], a["time"], a.get("method", "Linear"))
        return {"energy": arr(res)}
    raise ValueError(fn)

for case in json.loads(cases_path.read_text()):
    record = {"id": case["id"], "fn": case["fn"], "outputs": run_case(case)}
    (out_dir / f"{case['id']}.json").write_text(json.dumps(record))
    print(f"  {case['id']}")
PY

  echo
  echo "----- comparing against contract/golden -----"
  # Same --skip BMI_Category exclusion as hallmodel-core/proof/verify.sh — see
  # that file for the upstream-coercion-artifact explanation.
  "$PY" "$CORE/contract/compare.py" "$OUT_DIR" \
      --golden "$CORE/contract/golden" \
      --skip BMI_Category
  echo
  echo "PASS: parity holds."
} 2>&1 | tee "$LOG"
