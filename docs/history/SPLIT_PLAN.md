# Plan: split `bw-chocotonic` into a reusable C++ core + a Python consumer

Status: **executed 2026-06-19.** Final names: `hallmodel-core` (core),
`hallmodel-py` (Python consumer). New repos at `/Users/asdf/repos/hallmodel-core`
and `/Users/asdf/repos/hallmodel-py`. Both repos PASS the upstream parity
contract (18/18 cases, rtol=1e-9, atol=1e-12, --skip BMI_Category for the
upstream `as.numeric(character_matrix)` serialize artifact). GitHub push not
performed; awaiting user confirmation of remote names.

## Why this exists

PR [INSP-RH/bw#11](https://github.com/INSP-RH/bw/pull/11) was closed without
merge. The maintainer's position was reasonable: they don't want a structural
refactor of upstream just to subsidize a downstream Python port. The closing
agreement was to do the Python work in a separate repo.

The work in `bw-chocotonic` already proves the kernel extraction is sound:

- `src/include/bw/*.hpp` + `src/kernel/*.cpp` — pure C++ kernel, no Rcpp.
- `bindings/bw_cpp.cpp` + `bw_cpp/__init__.py` — pybind11 binding that
  consumes that kernel from Python.
- The C++-kernel refactor is **byte-identical to upstream R** under the
  official `contract/` gate maintained by INSP-RH (18/18 cases, with
  `-ffp-contract=off`).

That proof should be the foundation, not lost inside a fork that
also contains an entire R package the maintainer no longer wants modified.

The user-stated goal:

1. Extract the kernel into a clean repo whose _only_ job is "here is the bw
   math as a portable C++ library, with a proof it matches upstream R."
2. Demonstrate consumption from another language (Python via pybind11) in a
   second, separate repo.
3. Make it trivial for a third party to add a Julia / WASM / pure-C++ consumer
   later without forking either of the first two.

## Topology

Two new repositories:

### Repo A — the **core** (placeholder name: `bw-core`)

The portable C++ kernel + a vendored copy of upstream's parity contract +
the proof that the kernel passes it.

```
bw-core/
├── README.md                  # what this is, how to consume it, parity claim
├── LICENSE                    # carry forward INSP-RH/bw's license
├── include/bw/
│   ├── adult.hpp              # from bw-chocotonic/src/include/bw/adult.hpp
│   ├── child.hpp              # from bw-chocotonic/src/include/bw/child.hpp
│   └── energy.hpp             # from bw-chocotonic/src/include/bw/energy.hpp
├── src/
│   ├── adult.cpp              # from bw-chocotonic/src/kernel/adult.cpp
│   ├── child.cpp              # from bw-chocotonic/src/kernel/child.cpp
│   └── energy.cpp             # from bw-chocotonic/src/kernel/energy.cpp
├── CMakeLists.txt             # NEW — single static lib `bw_core`, INSTALL target
├── contract/                  # VENDORED from INSP-RH/bw `contract` branch
│   ├── README.md              # the parity guarantee, untouched
│   ├── cases.json
│   ├── golden/*.json          # 18 frozen reference outputs
│   ├── generate.R             # only needed to re-cut the contract
│   ├── generate.sh
│   ├── Dockerfile             # pinned r-base:4.6.0
│   └── compare.py             # tolerance-based parity gate
├── tests/
│   ├── parity_runner.cpp      # NEW — links bw_core, reads cases.json, writes outputs/*.json
│   ├── CMakeLists.txt         # NEW
│   └── outputs/               # gitignored; populated by running parity_runner
├── proof/                     # NEW — the committed evidence
│   ├── verify.sh              # build parity_runner, run it, run compare.py
│   ├── last_run.log           # PASS report, committed
│   └── outputs/*.json         # the 18 result JSONs from a real run (committed)
├── .github/workflows/parity.yml  # runs proof/verify.sh on every PR
└── docs/
    ├── HOW_TO_CONSUME.md      # for downstream binding authors
    └── ATTRIBUTION.md         # credit INSP-RH/bw, Hall et al.
```

**The "interface for other libraries"** = `include/bw/*.hpp` + the
`bw_core` static lib produced by `CMakeLists.txt`. Any downstream consumer
(Python, Julia, WASM, plain C++) depends on this repo as a CMake subproject or
a git submodule and links `bw_core`. They never need to read or rebuild the
contract — they trust that this repo's `proof/` directory is current.

**The "proof it works identically to the original repo"** = `proof/`. The
contract files come from upstream's `contract` branch (not invented here), the
runner is a C++ program that builds against `bw_core` and writes outputs in
the same schema `compare.py` already expects, and `compare.py` is the same
script the upstream maintainer ships. Verification reduces to:

```bash
./proof/verify.sh
# regenerates proof/outputs/*.json, runs contract/compare.py, exits 0 on parity
```

The committed `proof/last_run.log` + `proof/outputs/` is the offline proof —
someone reviewing the repo can `diff` the committed outputs against `contract/
golden/` themselves without building anything. CI re-derives it on every PR.

### Repo B — the **Python consumer** (placeholder name: `bw-py`)

A pybind11-backed Python package that depends on the core via git submodule
(or CMake `FetchContent`) and is the first proof that the "interface for other
libraries" claim is real.

```
bw-py/
├── README.md                  # API tour, install, parity claim ("depends on bw-core@<sha>")
├── LICENSE
├── pyproject.toml             # from bw-chocotonic/pyproject.toml
├── setup.py                   # from bw-chocotonic/setup.py, adjusted paths
├── bindings/
│   └── bw_cpp.cpp             # from bw-chocotonic/bindings/bw_cpp.cpp
├── bw_cpp/
│   └── __init__.py            # from bw-chocotonic/bw_cpp/__init__.py
├── external/bw-core/          # git submodule pointing at Repo A @ pinned sha
├── tests/
│   ├── test_adult.py
│   ├── test_child.py
│   ├── test_energy.py
│   └── test_contract_parity.py # runs cases.json through bw_cpp, checks vs golden
├── proof/                     # NEW — committed parity proof for this binding
│   ├── verify.sh              # pip install -e ., run cases through bw_cpp, compare
│   ├── last_run.log
│   └── outputs/*.json
└── .github/workflows/
    ├── parity.yml             # runs proof/verify.sh on every PR
    └── wheels.yml             # cibuildwheel for PyPI later, optional
```

`setup.py` already references `src/kernel/*.cpp` and `src/include` — those
paths re-point to `external/bw-core/src/*.cpp` and
`external/bw-core/include`. The submodule pin is the version contract: bumping
it is the only way the binding picks up kernel changes, and every bump
triggers parity re-verification.

`tests/test_contract_parity.py` uses the contract files from the submodule
(`external/bw-core/contract/cases.json` and `golden/`), so the test suite
itself is the parity gate — there is no separate "is this binding still
faithful?" question to answer.

## What we are NOT moving

- Anything under `R/`, `man/`, `vignettes/`, `inst/`, `NAMESPACE`,
  `DESCRIPTION`, `README.Rmd`, `src/*_rcpp.cpp`, `src/RcppExports.cpp`,
  `src/Makevars*`. That is upstream's R package, and the maintainer is the
  owner. The chocotonic fork can stay where it is as a record of PR #11.
- `bw-python/` (the pure-Python port). Per your answer, out of scope for this
  split. It can live on in `bw-chocotonic` or get its own repo later — that
  decision doesn't block this work.
- `tests/parity/` (the PR-11 bit-level snapshot gate). Superseded by the
  upstream `contract/` gate, which is the maintainer's own oracle and is
  what we should defer to.
- The chocotonic fork's `Dockerfile`, `.dockerignore`, `.Rbuildignore` — those
  were scaffolding for the closed PR.

## Step-by-step migration

This is the order of operations once names are picked and you say go. None of
these steps touch `bw-chocotonic` or `bw-INSP-RH`; both stay as-is for
reference until everything is verified.

1. **Init `bw-core`**
   - `git init`, copy LICENSE from `bw-INSP-RH`.
   - Copy `src/include/bw/*.hpp` → `include/bw/`.
   - Copy `src/kernel/*.cpp` → `src/`.
   - Vendor `bw-INSP-RH/contract/` → `contract/` (preserve as-is).
   - Write `CMakeLists.txt`: one `add_library(bw_core STATIC ...)` target, the
     three .cpp files, `target_include_directories` for `include/`, force
     `-ffp-contract=off` to match the contract.
   - Commit as "Import bw kernel + upstream contract".

2. **Add the parity runner in `bw-core`**
   - Write `tests/parity_runner.cpp`: reads `contract/cases.json`,
     dispatches on `fn`, calls into `bw::Adult` / `bw::Child` /
     `bw::EnergyBuilder`, serializes outputs in the contract's
     `{id, fn, outputs}` schema at 17 sig digits to `tests/outputs/<id>.json`.
   - Hook into CMake as a `parity_runner` executable.
   - Write `proof/verify.sh`: build, run, then `contract/compare.py
proof/outputs`. Capture log into `proof/last_run.log`.
   - Run it, commit the resulting `proof/outputs/` and `proof/last_run.log`.
   - Commit as "Add parity runner + frozen proof artifacts".

3. **Add CI in `bw-core`**
   - `.github/workflows/parity.yml`: ubuntu-latest, install python+cmake,
     run `proof/verify.sh`, fail on non-zero exit.
   - Commit, push, watch CI go green.

4. **Init `bw-py`**
   - `git init`, copy LICENSE.
   - `git submodule add <bw-core-url> external/bw-core` pinned at the green
     CI sha from step 3.
   - Copy `bindings/bw_cpp.cpp`, `bw_cpp/__init__.py`, `pyproject.toml`,
     `setup.py` from `bw-chocotonic`.
   - Edit `setup.py` paths: sources → `external/bw-core/src/*.cpp`,
     include_dirs → `external/bw-core/include`.
   - Commit as "Bootstrap pybind11 binding consuming bw-core".

5. **Add parity tests + proof in `bw-py`**
   - Write `tests/test_contract_parity.py` that reads
     `external/bw-core/contract/cases.json`, runs each through `bw_cpp`,
     and uses `external/bw-core/contract/compare.py` (or in-process
     equivalent) against `golden/`.
   - Write `proof/verify.sh`: `pip install -e .`, run the parity test,
     write outputs + log.
   - Run it, commit `proof/outputs/` and `proof/last_run.log`.
   - Commit as "Add parity tests + frozen proof artifacts".

6. **Add CI in `bw-py`** mirroring step 3.

7. **README pass on both repos**
   - `bw-core/README.md` answers: "I want to consume this from $LANGUAGE.
     How?" and points at `bw-py` as the worked example.
   - `bw-py/README.md` answers: "I want to compute body weight in Python
     and trust the numbers." and points at `bw-core` for the math.
   - Both attribute INSP-RH/bw and cite Hall et al.

8. **Archive note in `bw-chocotonic`**
   - Add a short note to its README ("the kernel and binding work has moved
     to `bw-core` and `bw-py`; this repo is preserved as the historical
     record of PR #11").
   - Leave `MAINTAINER_QUESTIONS.md` / `MAINTAINER_REPLY.md` where they are.

## How a third party adds a Julia / WASM / C# consumer later

Without re-explaining this in every future README, the recipe is:

1. New repo, `external/bw-core/` as a submodule pinned at a known-good sha.
2. Write a binding shim (Julia `ccall` + a thin C wrapper, or
   `Emscripten` for WASM, or P/Invoke for C#). All of these talk to the
   same `bw_core` static lib.
3. Reuse `external/bw-core/contract/cases.json` + `golden/` as the test
   suite. The parity gate is the same; only the harness changes.

This is the structural payoff of the split: the contract and the math live in
one place, and every consumer is small.

## Open questions (decide before step 1)

1. **Repo names.** You're picking. Once picked, swap throughout this doc and
   the submodule URL in step 4.
2. **License.** `bw-INSP-RH` carries an MIT-style `LICENSE` + `LICENSE.md`.
   Carry both forward verbatim into `bw-core` and `bw-py`, with a NOTICE
   crediting INSP-RH/bw. Confirm before commit.
3. **Submodule vs. `FetchContent` vs. vendored copy.** Default
   recommendation: git submodule for `bw-py`. It is the most explicit and
   reviewers can read the pinned sha at a glance. `FetchContent` is fine
   for downstream CMake consumers but is overkill for the Python repo.
4. **Where does `proof/` live in CI artifacts vs. committed?** Default:
   commit `proof/last_run.log` and `proof/outputs/*.json`, gitignore
   `proof/outputs/*.tmp`. The committed copy is the offline proof; CI
   regenerates and diffs.
5. **Re-cutting the contract.** Out of scope here. If upstream ever bumps
   `r-base` or adds a case, we `git pull --subtree=contract` in `bw-core`,
   re-run the parity runner, accept the new `proof/`. Document this in
   `bw-core/contract/README.md`'s "consumers" section so it's obvious.

## What this plan deliberately does not do

- No upstream PR. The maintainer was clear; the Python work belongs
  downstream.
- No retry of the kernel-extraction PR in disguise. The C++ kernel here is
  _our_ copy, not a fork of `src/`. If upstream ever wants to converge later,
  they can pull it in; we don't push.
- No build system gymnastics in `bw-core` beyond plain CMake. A consumer that
  wants Bazel / Buck / Meson can wrap CMake; we're not maintaining N build
  systems.
- No PyPI release in step 1. `bw-py` can stay `pip install -e .` until the
  parity story is settled and you decide to ship.
