"""Closed-form self-consistency check for adult_weight's Total_Expenditure.

Total_Expenditure (Hall eq 5) is not present in upstream INSP-RH/bw's
golden, so the contract gate skips it. This test is the substitute proof
of correctness:

    EE(t) = K + delta*BW + betaTEF*deltaEI + AT + gammaL*L + gammaF*F

K and delta are derived once at t=0 from the baseline state and the
published Hall constants. Every later EE value must satisfy the equation
exactly given the model-state trajectories (L, F, BW, AT, deltaEI), which
ARE parity-verified against R. So if EE matches the closed-form, EE is
consistent with the parity-verified dynamics by construction.

Constants and Mifflin-St Jeor coefficients are sourced from Hall 2011 +
the Mifflin-St Jeor equation and verified to match what the C++ kernel
uses internally (the parity gate would catch any mismatch on the dynamics).
"""
from __future__ import annotations

import numpy as np
import pytest

import bw_cpp

# Hall 2011 adult-model constants (converted from kJ to kcal at 0.23900573614).
# These are the same values the C++ kernel uses internally; that's why the
# closed-form check below succeeds.
GAMMA_F   = 3.107075     # kcal/kg/day, fat-mass cost coefficient
GAMMA_L   = 21.98853     # kcal/kg/day, lean-mass cost coefficient
BETA_TEF  = 0.1          # thermic effect of food fraction

# Mifflin-St Jeor RMR coefficients.
RMR_BW    = 9.99
RMR_HT    = 625.0
RMR_AGE   = 4.92
RMR_M     = 5.0          # male intercept
RMR_F     = -161.0       # female intercept


def _mifflin_rmr(bw, ht, age, sex):
    """Mifflin-St Jeor RMR. sex: 'male' or 'female'."""
    intercept = RMR_M if sex == "male" else RMR_F
    return RMR_BW * bw + RMR_HT * ht - RMR_AGE * age + intercept


@pytest.mark.parametrize("case", [
    dict(bw=76, ht=1.73, age=36, sex="male",   PAL=1.5),  # steady state
    dict(bw=90, ht=1.80, age=40, sex="male",   PAL=1.5,   # 500-kcal deficit
         EIchange=np.full((1, 365), -500.0)),
    dict(bw=65, ht=1.65, age=30, sex="female", PAL=1.5),  # steady state female
    dict(bw=80, ht=1.75, age=45, sex="male",   PAL=1.8),  # high PAL
])
def test_total_expenditure_matches_hall_eq5(case):
    """For every adult_weight case, Total_Expenditure must satisfy the
    closed-form Hall eq 5 against the returned state trajectories."""
    pal = case["PAL"]
    bw  = case["bw"]
    ht  = case["ht"]
    age = case["age"]
    sex = case["sex"]
    n_days = 365
    EIchange = case.get("EIchange", np.zeros((1, n_days)))

    res = bw_cpp.adult_weight(
        bw=bw, ht=ht, age=age, sex=sex, PAL=pal,
        EIchange=EIchange, days=n_days, dt=1.0,
    )

    F  = np.asarray(res["Fat_Mass"][0])
    L  = np.asarray(res["Lean_Mass"][0])
    BW = np.asarray(res["Body_Weight"][0])
    AT = np.asarray(res["Adaptive_Thermogenesis"][0])
    EE = np.asarray(res["Total_Expenditure"][0])

    # Derive K and delta at t=0 (mirrors the kernel's getK / getDelta).
    rmr = _mifflin_rmr(bw, ht, age, sex)
    delta = ((1.0 - BETA_TEF) * pal - 1.0) * rmr / bw
    K = rmr * pal - GAMMA_L * L[0] - GAMMA_F * F[0] - delta * BW[0]

    # deltaEI at each timestep: EIchange row, prepended with 0 for t=0 because
    # the kernel records EE(0) before the first integration step where TEF
    # already reflects deltaEI(0).
    dEI = np.asarray(EIchange[0])
    # The kernel emits EE for nsims+1 = 366 timesteps; align by prepending the
    # day-0 deltaEI to itself once (i.e. EE[i] uses dEI[i] for i in [0, nsims]).
    # deltaEI(0) reads EIchange[floor(0/dt)] = EIchange[0], so EE[0] uses
    # dEI[0]; EE[i] for i>=1 uses dEI[i-1] because TIME[i]=i and floor(i/1)=i
    # but we recompute t in the loop... actually deltaEI(TIME[ip]) = EIchange
    # at floor(TIME[ip]/dt). TIME[ip] = (i)*dt = i. floor(i/1) = i.
    # So EE[i] uses dEI[i] for i in [0, nsims-1]. EE[nsims] uses dEI[nsims-1]
    # if floor(nsims/1) >= len; but the kernel clamps idx to nrow-1.
    # Simplest robust alignment: dEI_aligned[i] = dEI[min(i, len(dEI)-1)].
    idx = np.minimum(np.arange(len(EE)), len(dEI) - 1)
    dEI_aligned = dEI[idx]

    expected_EE = (
        K
        + delta * BW
        + BETA_TEF * dEI_aligned
        + AT
        + GAMMA_L * L
        + GAMMA_F * F
    )

    np.testing.assert_allclose(
        EE, expected_EE, rtol=1e-9, atol=1e-9,
        err_msg=f"Total_Expenditure does not match Hall eq 5 for case {case}",
    )
