#!/usr/bin/env bash
# verify.sh — build the binding, run every contract case through bw_cpp,
# and assert parity via the contract's own compare.py.
#
# Uses uv to manage the build environment so the proof is reproducible
# regardless of the caller's Python state.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
CORE="$REPO_ROOT/external/hallmodel-core"
OUT_DIR="$SCRIPT_DIR/outputs"
LOG="$SCRIPT_DIR/last_run.log"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

cd "$REPO_ROOT"

{
  echo "----- hallmodel-py parity verification -----"
  echo "date:               $(date -u +%FT%TZ)"
  echo "host:               $(uname -srm)"
  echo "uv:                 $(uv --version 2>/dev/null || echo 'not installed')"
  echo "core submodule sha: $(git -C "$CORE" rev-parse HEAD)"
  echo "repo:               $REPO_ROOT"
  echo

  if [[ ! -e "$CORE/contract/cases.json" ]]; then
    echo "ERROR: submodule not initialized; run: git submodule update --init --recursive" >&2
    exit 2
  fi

  if ! command -v uv >/dev/null; then
    echo "ERROR: uv not installed. See https://docs.astral.sh/uv/" >&2
    exit 2
  fi

  echo "----- syncing deps + building extension -----"
  uv sync
  uv pip install -e . --quiet

  echo
  echo "----- driving cases through bw_cpp -----"
  uv run python - "$CORE/contract/cases.json" "$OUT_DIR" <<'PY'
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
  # Same --skip set as hallmodel-core/proof/verify.sh:
  #   BMI_Category      — upstream as.numeric(character_matrix) coercion artifact
  #   Total_Expenditure — additive output not in upstream golden (validated by
  #                       tests/test_total_expenditure.py closed-form check)
  uv run python "$CORE/contract/compare.py" "$OUT_DIR" \
      --golden "$CORE/contract/golden" \
      --skip BMI_Category,Total_Expenditure
  echo
  echo "PASS: parity holds."
} 2>&1 | tee "$LOG"
