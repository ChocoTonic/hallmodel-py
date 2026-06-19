"""bw_cpp — Python interface to the bw dynamic body-weight models, backed by the
pure-C++ kernel (the same kernel the R package compiles).

Python ergonomics, C++ performance, and — built in the pinned toolchain with
-ffp-contract=off — output bit-identical to the upstream R/C++ results.

This module is a thin orchestration shim mirroring R/adult_weight.R and
R/child_weight.R: it validates inputs, converts sex to 0/1, fills defaults, and
dispatches to the compiled kernel in _bw_cpp. All numeric work is in C++.
"""
import math

import numpy as np

import _bw_cpp

__all__ = ["adult_weight", "child_weight", "EnergyBuilder",
           "child_reference_FFMandFM", "child_reference_EI"]


def _sex_to_num(sex):
    """'male'->0, 'female'->1 (accepts scalar/list/array of strings or numbers)."""
    arr = np.atleast_1d(np.asarray(sex, dtype=object))
    out = np.zeros(len(arr), dtype=float)
    for i, s in enumerate(arr):
        if isinstance(s, str):
            if s == "female":
                out[i] = 1.0
            elif s != "male":
                raise ValueError(f"Invalid sex '{s}'. Use 'male' or 'female'.")
        else:
            out[i] = float(s)
    return out


def _vec(x, n):
    a = np.atleast_1d(np.asarray(x, dtype=float))
    if a.size == 1 and n > 1:
        a = np.full(n, a.item())
    return np.ascontiguousarray(a, dtype=float)


def adult_weight(bw, ht, age, sex, *, EIchange=None, NAchange=None, EI=None,
                 fat=None, PAL=1.5, pcarb_base=0.5, pcarb=None, days=365, dt=1.0,
                 check_values=True):
    """Adult body-weight trajectory. Mirrors R::adult_weight."""
    bw = _vec(bw, 1); n = bw.size
    ht = _vec(ht, n); age = _vec(age, n)
    newsex = _sex_to_num(sex)
    PAL = _vec(PAL, n); pcarb_base = _vec(pcarb_base, n)
    pcarb = pcarb_base.copy() if pcarb is None else _vec(pcarb, n)

    ncol = abs(math.ceil(days / dt))
    EIchange = np.zeros((n, ncol)) if EIchange is None else np.atleast_2d(np.asarray(EIchange, float))
    NAchange = np.zeros((n, ncol)) if NAchange is None else np.atleast_2d(np.asarray(NAchange, float))

    fat_arr = np.full(n, np.nan) if fat is None else _vec(fat, n)
    isfat = bool(np.any(np.isnan(fat_arr)))            # True == fat NOT supplied
    if EI is None:
        EI_arr = np.full(n, np.nan)
    else:
        EI_arr = _vec(EI, n)
    isEI = bool(np.any(np.isnan(EI_arr)))              # True == EI NOT supplied

    # kernel expects EIchange/NAchange transposed (rows = day, cols = individual)
    EIc = np.ascontiguousarray(EIchange.T, dtype=float)
    NAc = np.ascontiguousarray(NAchange.T, dtype=float)
    cd = float(math.ceil(days))

    if isfat and isEI:
        res = _bw_cpp.adult_baseline(bw, ht, age, newsex, EIc, NAc, PAL, pcarb_base, pcarb, dt, cd, check_values)
    elif (not isEI) and isfat:
        res = _bw_cpp.adult_ei(bw, ht, age, newsex, EIc, NAc, PAL, pcarb_base, pcarb, dt, EI_arr, cd, check_values, True)
    elif isEI and (not isfat):
        res = _bw_cpp.adult_ei(bw, ht, age, newsex, EIc, NAc, PAL, pcarb_base, pcarb, dt, fat_arr, cd, check_values, False)
    else:
        res = _bw_cpp.adult_ei_fat(bw, ht, age, newsex, EIc, NAc, PAL, pcarb_base, pcarb, dt, EI_arr, fat_arr, cd, check_values)

    if res["Correct_Values"] is False:
        raise ValueError("One of the variables takes negative/NaN/NA/infinity values")
    return res


def child_reference_FFMandFM(age, sex):
    """Reference FFM/FM. Mirrors R::child_reference_FFMandFM."""
    age = _vec(age, 1)
    return _bw_cpp.mass_reference(age, _sex_to_num(sex))


def child_reference_EI(age, sex, FM, FFM, days, dt=1.0):
    """Default child energy intake. Mirrors R::child_reference_EI.

    NOTE the argument positions: R passes (age, sex, FM, FFM) into a wrapper whose
    params are (age, sex, FFM, FM) — i.e. FM and FFM occupy swapped slots. We
    reproduce that exactly, then transpose the result.
    """
    age = _vec(age, 1)
    out = _bw_cpp.intake_reference(age, _sex_to_num(sex),
                                   np.asarray(FM, float), np.asarray(FFM, float),
                                   float(days), float(dt))
    return np.ascontiguousarray(np.asarray(out).T, dtype=float)


def child_weight(age, sex, *, FM=None, FFM=None, EI=None, richardson_params=None,
                 days=365, dt=1.0, check_values=True):
    """Child weight trajectory. Mirrors R::child_weight."""
    age = _vec(age, 1); n = age.size
    newsex = _sex_to_num(sex)
    if FM is None or FFM is None:
        ref = child_reference_FFMandFM(age, sex)
        FM = ref["FM"] if FM is None else _vec(FM, n)
        FFM = ref["FFM"] if FFM is None else _vec(FFM, n)
    else:
        FM = _vec(FM, n); FFM = _vec(FFM, n)

    rp = richardson_params
    have_rich = rp is not None and all(rp.get(k) is not None for k in ("K", "Q", "A", "B", "nu", "C"))

    if EI is None and not have_rich:
        EI = child_reference_EI(age, sex, FM, FFM, days, dt)

    if EI is not None:
        EImat = np.atleast_2d(np.asarray(EI, dtype=float))
        return _bw_cpp.child_classic(age, newsex, np.asarray(FFM, float), np.asarray(FM, float),
                                     np.ascontiguousarray(EImat), float(days), float(dt), check_values)
    return _bw_cpp.child_richardson(age, newsex, np.asarray(FFM, float), np.asarray(FM, float),
                                    float(rp["K"]), float(rp["Q"]), float(rp["A"]), float(rp["B"]),
                                    float(rp["nu"]), float(rp["C"]), float(days), float(dt), check_values)


class EnergyBuilder:
    """Energy-intake interpolation (deterministic methods), backed by C++."""

    def build(self, energy, time, method="Linear"):
        energy = np.atleast_2d(np.asarray(energy, dtype=float))
        time = np.ascontiguousarray(np.asarray(time, dtype=float))
        return _bw_cpp.energy_builder(np.ascontiguousarray(energy), time, str(method))
