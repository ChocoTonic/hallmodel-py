"""hallmodel — Python interface to the Hall body-weight dynamics models.

This is a thin alias over the `bw_cpp` module so callers can write
`from hallmodel import adult_weight` to match the PyPI package name. The
actual implementation lives in `bw_cpp` (the binding module name was
chosen to match the historical INSP-RH/bw Rcpp wrapper layout).

Both import paths refer to the same code; pick whichever reads better in
your call site.
"""
from bw_cpp import (
    EnergyBuilder,
    adult_weight,
    child_reference_EI,
    child_reference_FFMandFM,
    child_weight,
)

__all__ = [
    "adult_weight",
    "child_weight",
    "child_reference_EI",
    "child_reference_FFMandFM",
    "EnergyBuilder",
]
