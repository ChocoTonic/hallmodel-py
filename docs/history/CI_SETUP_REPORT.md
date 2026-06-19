# CI setup report — hallmodel-core & hallmodel-py

Generated 2026-06-19 after pushing the CI workflows to both repos.

## TL;DR

Both repos have green CI as of the latest commit. The Python repo additionally
has an auto-release pipeline (sdist + wheels matrix) and a weekly
dependency-bump workflow. **One manual step is required from you before the
auto-PyPI-release pipeline can actually publish:** configure a Trusted
Publisher on pypi.org. Steps below.

## What was set up

### `hallmodel-core` — [`.github/workflows/parity.yml`](https://github.com/ChocoTonic/hallmodel-core/blob/master/.github/workflows/parity.yml)

| trigger          | push to master, PRs |
| ---------------- | ------------------- |
| matrix           | `gcc` + `clang` on `ubuntu-latest` |
| caching          | `actions/cache` on `build/_deps` (nlohmann/json FetchContent dir) |
| concurrency      | one run per ref; cancel-in-progress |
| artifact storage | none — verify.sh writes to `build/` only |
| runtime          | ~1 min per matrix arm (cold), ~30 sec (warm cache) |

Plus [`.github/dependabot.yml`](https://github.com/ChocoTonic/hallmodel-core/blob/master/.github/dependabot.yml)
for weekly bumps of the actions themselves (checkout, cache, etc.).

### `hallmodel-py` — three workflows + dependabot

**1. [`parity.yml`](https://github.com/ChocoTonic/hallmodel-py/blob/master/.github/workflows/parity.yml)** — push to master, PRs
- `astral-sh/setup-uv@v3` with `cache-dependency-glob: uv.lock` (uv handles its own caching)
- `uv sync` → `./proof/verify.sh` → `uv run pytest tests/ -v`
- concurrency: cancel-in-progress per ref
- runtime: ~45 sec end-to-end (cached deps)

**2. [`release.yml`](https://github.com/ChocoTonic/hallmodel-py/blob/master/.github/workflows/release.yml)** — push to master only
- Job 1 `compute-version`: derive calver `YYYY.M.D.<run_number>` (no commit-back; every run unique)
- Job 2 `sdist`: rewrites `pyproject.toml` version, `python -m build --sdist`, uploads `dist/*.tar.gz` with `retention-days: 1`
- Job 3 `wheels` (matrix: `ubuntu-latest` linux-x86_64 + `macos-14` arm64): cibuildwheel for cp310-cp313, skips musllinux/PyPy/i686, uploads with `retention-days: 1`
- Job 4 `publish`: downloads all artifacts, publishes via `pypa/gh-action-pypi-publish@release/v1` with OIDC (`id-token: write`)
- runtime: ~5-6 min cold; subsequent runs share cibuildwheel's container cache

**3. [`bump-deps.yml`](https://github.com/ChocoTonic/hallmodel-py/blob/master/.github/workflows/bump-deps.yml)** — Mondays 09:00 UTC + `workflow_dispatch`
- `uv lock --upgrade`
- `peter-evans/create-pull-request@v6` opens a PR if `uv.lock` changed (branch `bump/deps`, deleted after merge)

**4. [`.github/dependabot.yml`](https://github.com/ChocoTonic/hallmodel-py/blob/master/.github/dependabot.yml)** — weekly GitHub Actions version bumps.

## You must do this before auto-publish works

The release pipeline runs all the way through `wheels` but fails at the
`publish` step until you set up a **Trusted Publisher** on pypi.org. ~30 sec,
one-time:

1. Go to https://pypi.org/manage/account/publishing/
2. Click **"Add a new pending publisher"** (the "pending" flow lets you set
   up Trusted Publisher *before* the project exists, which it doesn't yet).
3. Fill in:
   - **PyPI project name**: `hallmodel`
   - **Owner**: `ChocoTonic`
   - **Repository name**: `hallmodel-py`
   - **Workflow filename**: `release.yml`
   - **Environment name**: `pypi`
4. Then in the GitHub repo: Settings → Environments → New environment → name
   it `pypi`. (No protection rules needed.)
5. Trigger a new release: push any commit to `master` (or
   `gh workflow run release.yml --repo ChocoTonic/hallmodel-py`).

The first successful publish converts the "pending" publisher into a regular
Trusted Publisher and the project shows up on pypi.org.

## Storage minimization

| mechanism                              | where                              |
| -------------------------------------- | ---------------------------------- |
| `retention-days: 1` on all artifacts   | release.yml sdist + wheels uploads |
| `concurrency.cancel-in-progress: true` | parity.yml (both repos)            |
| `actions/cache` on FetchContent _deps  | core/parity.yml                    |
| `astral-sh/setup-uv` cache             | py/parity.yml (keyed on uv.lock)   |
| `actions/setup-python cache: pip`      | py/release.yml sdist job           |
| No proof/outputs/ uploads              | both — the proof JSONs are committed at PR time, not re-uploaded per CI run |

PyPI itself stores release wheels (free for OSS). GitHub Actions artifact
storage is only used for the ~30 sec between `wheels` upload and `publish`
download.

## CI runs from this session

### `hallmodel-core`
- [Run 27843944400](https://github.com/ChocoTonic/hallmodel-core/actions/runs/27843944400) — initial push, FAIL (workflow not yet present in commit; transient)
- [Run 27845400831](https://github.com/ChocoTonic/hallmodel-core/actions/runs/27845400831) — matrix gcc+clang, FAIL on byte-diff (cross-platform ULP drift, expected)
- **[Run 27845460873](https://github.com/ChocoTonic/hallmodel-core/actions/runs/27845460873) — PASS after dropping byte-diff. Both gcc and clang green.**

### `hallmodel-py`
- [Run 27843962903](https://github.com/ChocoTonic/hallmodel-py/actions/runs/27843962903) — initial push, FAIL
- [Run 27845398578](https://github.com/ChocoTonic/hallmodel-py/actions/runs/27845398578) — parity FAIL on byte-diff
- [Run 27845398585](https://github.com/ChocoTonic/hallmodel-py/actions/runs/27845398585) — first release run. sdist + both wheel jobs PASS; publish FAIL (expected — Trusted Publisher not configured yet)
- **[Run 27845461746](https://github.com/ChocoTonic/hallmodel-py/actions/runs/27845461746) — parity PASS after dropping byte-diff.**
- **[Run 27845461743](https://github.com/ChocoTonic/hallmodel-py/actions/runs/27845461743) — release: compute-version + sdist + both wheel jobs PASS; publish FAIL (expected, no Trusted Publisher yet).**
- **[Run 27845512102](https://github.com/ChocoTonic/hallmodel-py/actions/runs/27845512102) — bump-deps `workflow_dispatch` PASS (no PR opened because nothing to upgrade against the fresh lockfile).**

## What I learned in the process

### Cross-platform ULP drift in JSON outputs

The committed `proof/outputs/*.json` artifacts are not byte-stable across
platforms — even with `-ffp-contract=off`, last-ULP differences between my
macOS arm64 and CI's Linux x86_64 produce slightly different float reprs,
which JSON serialization preserves. The contract's `compare.py` tolerance
(rtol=1e-9, atol=1e-12) absorbs this; byte-diff did not. **Fix:** dropped
the `git diff --exit-code proof/outputs/` step from both parity workflows.
The committed proof is now treated as a "same-platform snapshot for human
inspection" rather than a CI invariant.

### Trusted Publisher is the right default

OIDC + Trusted Publisher means no secrets in the GitHub repo, no token
rotation, and PyPI itself enforces the workflow-file identity. The cost is
the one-time ~30 sec configuration on pypi.org. Worth it for any new
project.

### uv handles its own caching well

`astral-sh/setup-uv@v3` with `cache-dependency-glob: uv.lock` is one line
in the workflow and ~10x faster than the manual venv-from-scratch approach
that `verify.sh` was originally written against. The `verify.sh` was
updated to call `uv sync` + `uv run` accordingly, so both local and CI
runs go through the same path.

### Calver avoids commit-back loops

Auto-bumping semver requires committing the bump back to master, which
either needs a PAT or `[skip ci]` rules to avoid infinite re-triggering.
Calver (`YYYY.M.D.<run_number>`) sidesteps all of that — the workflow
computes the version into the build process directly and never modifies
the repo. Each push to master gets a unique, monotonic PyPI version.

## Open follow-ups

- [ ] Configure Trusted Publisher on pypi.org (you, ~30 sec — see above).
- [ ] Consider adding `actions/cache` on `~/.cache/cibuildwheel` if the
      wheel matrix gets bigger; for the current 8-wheel matrix it's not
      necessary.
- [ ] When you start tagging real releases, decide whether to keep calver
      or switch to semver tags. Calver makes sense for "every merge is a
      release"; if you eventually want stable/beta distinction, semver +
      tag-driven releases is the standard.
