# hallmodel-py

Python interface to the [Hall](https://www.niddk.nih.gov/about-niddk/staff-directory/biography/hall-kevin)
adult- and child- body-weight dynamics models, backed by the C++ kernel in
[hallmodel-core](../hallmodel-core) (vendored here as a git submodule).

The kernel is the same math the R package [`INSP-RH/bw`](https://github.com/INSP-RH/bw)
compiles. Compiled in matched toolchains with `-ffp-contract=off`, the
outputs are byte-for-byte reproducible against the upstream parity contract;
under the contract's published tolerance (`rtol=1e-9`, `atol=1e-12`), all 18
contract cases pass.

This is the first reference consumer of `hallmodel-core` — it is also the
worked example for "here is how you write a new language binding against the
core."

---

## Install

```bash
git clone --recurse-submodules <repo-url> hallmodel-py
cd hallmodel-py
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Build needs a C++17 compiler and `pybind11` (declared in `pyproject.toml`).

If you cloned without `--recurse-submodules`:

```bash
git submodule update --init --recursive
```

## Use

```python
import bw_cpp

# Adult model — single individual, baseline EI from Mifflin-St Jeor
res = bw_cpp.adult_weight(bw=76, ht=1.73, age=36, sex="male")
print(res["Body_Weight"].shape)       # (1, 366)

# Adult with a 500-kcal deficit over 365 days
import numpy as np
res = bw_cpp.adult_weight(
    bw=90, ht=1.80, age=40, sex="male",
    EIchange=np.full((1, 365), -500.0),
)

# Child model — auto FFM/FM/EI defaults from age + sex
res = bw_cpp.child_weight(age=6, sex="male", days=365)

# Energy interpolation
out = bw_cpp.EnergyBuilder().build(
    energy=np.array([[2000, 2200, 1800]]),
    time=np.array([0, 5, 10]),
    method="Linear",
)
```

See the docstrings in [`bw_cpp/__init__.py`](bw_cpp/__init__.py) for the full
API, and the upstream [R wrappers](https://github.com/INSP-RH/bw/tree/master/R)
for the semantics of each parameter — they are the same.

## Parity proof

`./proof/verify.sh` builds the binding against the pinned `hallmodel-core`
submodule, drives all 18 contract cases through `bw_cpp`, and asserts the
contract's tolerance via `contract/compare.py`. Exit 0 = parity holds.

```bash
./proof/verify.sh
```

The committed [`proof/last_run.log`](proof/last_run.log) and
[`proof/outputs/`](proof/outputs/) are the frozen evidence of the most
recent green run. CI re-runs them on every PR. The pinned submodule sha is
the version contract: bumping it triggers a re-verify.

The one excluded field is `BMI_Category` — the contract's `generate.R`
coerces character matrices through `as.numeric()`, producing a column of
literal `"NA"` strings in every adult golden. See
[`hallmodel-core/proof/verify.sh`](external/hallmodel-core/proof/verify.sh)
for the full explanation.

## How this maps to upstream

| upstream R                            | here                          |
| ------------------------------------- | ----------------------------- |
| `INSP-RH/bw::adult_weight()`          | `bw_cpp.adult_weight()`       |
| `INSP-RH/bw::child_weight()`          | `bw_cpp.child_weight()`       |
| `INSP-RH/bw::child_reference_EI()`    | `bw_cpp.child_reference_EI()` |
| `INSP-RH/bw::child_reference_FFMandFM()` | `bw_cpp.child_reference_FFMandFM()` |
| `INSP-RH/bw::EnergyBuilder()`         | `bw_cpp.EnergyBuilder().build()` |

Argument names, semantics, and defaults all match `INSP-RH/bw`'s R wrappers
because this Python shim was deliberately written as a direct port of those
wrappers. The contract gate enforces it.

## License

MIT, carried forward from [`INSP-RH/bw`](https://github.com/INSP-RH/bw).

## Citing

Cite the original `bw` package and Hall et al.'s underlying papers. See the
README of [`INSP-RH/bw`](https://github.com/INSP-RH/bw) and
[`hallmodel-core/docs/ATTRIBUTION.md`](external/hallmodel-core/docs/ATTRIBUTION.md).
