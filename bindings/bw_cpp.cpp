// pybind11 bindings exposing the pure-C++ bw kernel (src/kernel, src/include)
// to Python — the same kernel the R package compiles, so results are identical.
//
// These mirror the [[Rcpp::export]] wrappers in src/*_rcpp.cpp one-to-one
// (same arguments, same call patterns), but marshal NumPy arrays instead of
// Rcpp types. The thin orchestration shim lives in Python (bw_cpp/__init__.py),
// mirroring R/*.R.
//
// Build with -ffp-contract=off (see pyproject) so the arithmetic matches the
// contract's golden bit-for-bit when compiled in the same toolchain.

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <cmath>
#include <cstddef>
#include <stdexcept>
#include <string>
#include <vector>

#include "bw/adult.hpp"
#include "bw/child.hpp"
#include "bw/energy.hpp"

namespace py = pybind11;

// ---- input marshaling ------------------------------------------------------

static std::vector<double> vec1d(const py::array_t<double>& a) {
    auto b = a.template unchecked<1>();
    std::vector<double> out(static_cast<std::size_t>(b.shape(0)));
    for (py::ssize_t i = 0; i < b.shape(0); ++i) out[static_cast<std::size_t>(i)] = b(i);
    return out;
}

// 2D NumPy (row-major) -> bw::Matrix preserving (i, j).
static bw::Matrix mat2d(const py::array_t<double>& a) {
    auto b = a.template unchecked<2>();
    bw::Matrix m(static_cast<std::size_t>(b.shape(0)), static_cast<std::size_t>(b.shape(1)));
    for (py::ssize_t i = 0; i < b.shape(0); ++i)
        for (py::ssize_t j = 0; j < b.shape(1); ++j)
            m(static_cast<std::size_t>(i), static_cast<std::size_t>(j)) = b(i, j);
    return m;
}

// ---- output marshaling -----------------------------------------------------

static py::array_t<double> from_mat(const bw::Matrix& m) {
    py::array_t<double> out({m.nrow, m.ncol});
    auto r = out.mutable_unchecked<2>();
    for (std::size_t i = 0; i < m.nrow; ++i)
        for (std::size_t j = 0; j < m.ncol; ++j)
            r(i, j) = m(i, j);
    return out;
}

static py::array_t<double> from_vec(const std::vector<double>& v) {
    py::array_t<double> out(static_cast<py::ssize_t>(v.size()));
    auto r = out.mutable_unchecked<1>();
    for (std::size_t i = 0; i < v.size(); ++i) r(static_cast<py::ssize_t>(i)) = v[i];
    return out;
}

// Child result matrices are laid out data[i + nind*j]; reshape to (nind, nsteps).
static py::array_t<double> from_child(const std::vector<double>& data,
                                      std::size_t nind, std::size_t nsteps) {
    py::array_t<double> out({nind, nsteps});
    auto r = out.mutable_unchecked<2>();
    for (std::size_t i = 0; i < nind; ++i)
        for (std::size_t j = 0; j < nsteps; ++j)
            r(i, j) = data[i + nind * j];
    return out;
}

static py::dict adult_result(const bw::AdultResult& res) {
    // BMI_Category: list of per-individual lists of strings (rows = individuals).
    py::list cat;
    for (std::size_t i = 0; i < res.BMI_Category.nrow; ++i) {
        py::list row;
        for (std::size_t j = 0; j < res.BMI_Category.ncol; ++j)
            row.append(res.BMI_Category(i, j));
        cat.append(row);
    }
    py::dict d;
    d["Time"]                   = from_vec(res.Time);
    d["Age"]                    = from_mat(res.Age);
    d["Adaptive_Thermogenesis"] = from_mat(res.Adaptive_Thermogenesis);
    d["Extracellular_Fluid"]    = from_mat(res.Extracellular_Fluid);
    d["Glycogen"]               = from_mat(res.Glycogen);
    d["Fat_Mass"]               = from_mat(res.Fat_Mass);
    d["Lean_Mass"]              = from_mat(res.Lean_Mass);
    d["Body_Weight"]            = from_mat(res.Body_Weight);
    d["Body_Mass_Index"]        = from_mat(res.Body_Mass_Index);
    d["BMI_Category"]           = cat;
    d["Energy_Intake"]          = from_mat(res.Energy_Intake);
    d["Correct_Values"]         = res.Correct_Values;
    d["Model_Type"]             = res.Model_Type;
    return d;
}

static py::dict child_result(const bw::ChildRK4Result& R) {
    py::dict d;
    d["Time"]           = from_vec(R.Time);
    d["Age"]            = from_child(R.Age,           R.nind, R.nsteps);
    d["Fat_Free_Mass"]  = from_child(R.Fat_Free_Mass, R.nind, R.nsteps);
    d["Fat_Mass"]       = from_child(R.Fat_Mass,      R.nind, R.nsteps);
    d["Body_Weight"]    = from_child(R.Body_Weight,   R.nind, R.nsteps);
    d["Correct_Values"] = R.Correct_Values;
    d["Model_Type"]     = std::string("Children");
    return d;
}

// ---- exported functions (mirror src/*_rcpp.cpp) ----------------------------

static py::dict adult_baseline(py::array_t<double> bw, py::array_t<double> ht,
        py::array_t<double> age, py::array_t<double> sex,
        py::array_t<double> EIchange, py::array_t<double> NAchange,
        py::array_t<double> PAL, py::array_t<double> pcarb_base,
        py::array_t<double> pcarb, double dt, double days, bool checkValues) {
    bw::Adult P(vec1d(bw), vec1d(ht), vec1d(age), vec1d(sex),
                mat2d(EIchange), mat2d(NAchange),
                vec1d(PAL), vec1d(pcarb), vec1d(pcarb_base), dt, checkValues);
    return adult_result(P.rk4(days));
}

static py::dict adult_ei(py::array_t<double> bw, py::array_t<double> ht,
        py::array_t<double> age, py::array_t<double> sex,
        py::array_t<double> EIchange, py::array_t<double> NAchange,
        py::array_t<double> PAL, py::array_t<double> pcarb_base,
        py::array_t<double> pcarb, double dt, py::array_t<double> extradata,
        double days, bool checkValues, bool isEnergy) {
    bw::Adult P(vec1d(bw), vec1d(ht), vec1d(age), vec1d(sex),
                mat2d(EIchange), mat2d(NAchange),
                vec1d(PAL), vec1d(pcarb), vec1d(pcarb_base), dt,
                vec1d(extradata), checkValues, isEnergy);
    return adult_result(P.rk4(days));
}

static py::dict adult_ei_fat(py::array_t<double> bw, py::array_t<double> ht,
        py::array_t<double> age, py::array_t<double> sex,
        py::array_t<double> EIchange, py::array_t<double> NAchange,
        py::array_t<double> PAL, py::array_t<double> pcarb_base,
        py::array_t<double> pcarb, double dt, py::array_t<double> input_EI,
        py::array_t<double> input_fat, double days, bool checkValues) {
    bw::Adult P(vec1d(bw), vec1d(ht), vec1d(age), vec1d(sex),
                mat2d(EIchange), mat2d(NAchange),
                vec1d(PAL), vec1d(pcarb), vec1d(pcarb_base), dt,
                vec1d(input_EI), vec1d(input_fat), checkValues);
    return adult_result(P.rk4(days));
}

static py::dict child_classic(py::array_t<double> age, py::array_t<double> sex,
        py::array_t<double> FFM, py::array_t<double> FM,
        py::array_t<double> EIntake, double days, double dt, bool checkValues) {
    auto b = EIntake.unchecked<2>();
    std::size_t nr = static_cast<std::size_t>(b.shape(0));
    std::size_t nc = static_cast<std::size_t>(b.shape(1));
    std::vector<double> ei(nr * nc);
    for (std::size_t r = 0; r < nr; ++r)
        for (std::size_t c = 0; c < nc; ++c) ei[r * nc + c] = b(static_cast<py::ssize_t>(r), static_cast<py::ssize_t>(c));
    bw::Child P(vec1d(age), vec1d(sex), vec1d(FFM), vec1d(FM), ei, nr, nc, dt, checkValues);
    return child_result(P.rk4(days - 1));   // days-1: see child_rcpp.cpp
}

static py::dict child_richardson(py::array_t<double> age, py::array_t<double> sex,
        py::array_t<double> FFM, py::array_t<double> FM,
        double K, double Q, double A, double B, double nu, double C,
        double days, double dt, bool checkValues) {
    bw::Child P(vec1d(age), vec1d(sex), vec1d(FFM), vec1d(FM), K, Q, A, B, nu, C, dt, checkValues);
    return child_result(P.rk4(days - 1));
}

// mass_reference_wrapper: returns {FM, FFM} (mirrors src/child_rcpp.cpp).
static py::dict mass_reference(py::array_t<double> age, py::array_t<double> sex) {
    std::vector<double> age_v = vec1d(age), sex_v = vec1d(sex);
    std::vector<double> ffm(age_v.size(), 0.0), fm(age_v.size(), 0.0);
    std::vector<double> ei(1, 0.0);
    bw::Child P(age_v, sex_v, ffm, fm, ei, 1, 1, 1.0, false);
    py::dict d;
    d["FM"]  = from_vec(P.FMReference(age_v));
    d["FFM"] = from_vec(P.FFMReference(age_v));
    return d;
}

// intake_reference_wrapper(age, sex, FFM, FM, days, dt) -> (nind, ncols).
static py::array_t<double> intake_reference(py::array_t<double> age, py::array_t<double> sex,
        py::array_t<double> FFM, py::array_t<double> FM, double days, double dt) {
    std::vector<double> age_v = vec1d(age), sex_v = vec1d(sex);
    std::vector<double> ffm_v = vec1d(FFM), fm_v = vec1d(FM);
    std::vector<double> ei(1, 0.0);
    bw::Child P(age_v, sex_v, ffm_v, fm_v, ei, 1, 1, dt, false);
    std::size_t nind = age_v.size();
    std::size_t ncols = static_cast<std::size_t>(std::floor(days / dt) + 1);
    bw::Matrix out(nind, ncols);
    for (double i = 0; i < std::floor(days / dt) + 1; i += 1.0) {
        std::vector<double> t(nind);
        for (std::size_t k = 0; k < nind; ++k) t[k] = age_v[k] + dt * i / 365.0;
        std::vector<double> col = P.IntakeReference(t);
        std::size_t ci = static_cast<std::size_t>(i);
        for (std::size_t k = 0; k < nind; ++k) out(k, ci) = col[k];
    }
    return from_mat(out);
}

// EnergyBuilder: deterministic methods only. Energy is (nrow, ntimes).
static py::array_t<double> energy_builder(py::array_t<double> Energy,
        py::array_t<double> Time, const std::string& interpol) {
    auto e = Energy.unchecked<2>();
    std::size_t nrow = static_cast<std::size_t>(e.shape(0));
    std::size_t nt   = static_cast<std::size_t>(e.shape(1));
    std::vector<double> tvec = vec1d(Time);
    // build_deterministic expects column-major Energy[r + c*nrow]
    std::vector<double> ecol(nrow * nt);
    for (std::size_t r = 0; r < nrow; ++r)
        for (std::size_t c = 0; c < nt; ++c) ecol[r + c * nrow] = e(static_cast<py::ssize_t>(r), static_cast<py::ssize_t>(c));
    std::size_t ncols = bw::energy::output_ncols(tvec.data(), tvec.size());
    std::vector<double> evals(nrow * ncols, 0.0);
    bw::energy::Method m;
    if (!bw::energy::parse_method(interpol.c_str(), &m))
        throw std::invalid_argument("unknown/unsupported interpolation: " + interpol);
    bw::energy::build_deterministic(ecol.data(), nrow, nt, tvec.data(), m, evals.data());
    // evals column-major -> (nrow, ncols)
    bw::Matrix out(nrow, ncols);
    for (std::size_t r = 0; r < nrow; ++r)
        for (std::size_t c = 0; c < ncols; ++c) out(r, c) = evals[r + c * nrow];
    return from_mat(out);
}

PYBIND11_MODULE(_bw_cpp, m) {
    m.doc() = "C++ kernel bindings for the bw dynamic body-weight models.";
    m.def("adult_baseline", &adult_baseline);
    m.def("adult_ei", &adult_ei);
    m.def("adult_ei_fat", &adult_ei_fat);
    m.def("child_classic", &child_classic);
    m.def("child_richardson", &child_richardson);
    m.def("mass_reference", &mass_reference);
    m.def("intake_reference", &intake_reference);
    m.def("energy_builder", &energy_builder);
}
