# Historical context

These two documents are the migration record from the
`ChocoTonic/bw` fork into the present two-repo split
(`hallmodel-core` + `hallmodel-py`):

- [`SPLIT_PLAN.md`](SPLIT_PLAN.md) — the original design + execution plan
  for separating the bw kernel from the R package, with the named
  rationale that informed the file/repo layout you see today.
- [`CI_SETUP_REPORT.md`](CI_SETUP_REPORT.md) — the CI-build-out report
  documenting the uv-based workflow, the auto-PyPI release pipeline, the
  consolidation of dep-bump flows onto Dependabot, and the Trusted
  Publisher setup.

The fork itself was deleted once the migration was complete. The PR that
the split was originally proposed against
([INSP-RH/bw#11](https://github.com/INSP-RH/bw/pull/11)) is closed; its
conversation remains visible on the upstream side and is the canonical
record of *why* this work moved downstream.
