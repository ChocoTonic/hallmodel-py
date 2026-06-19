"""Build the C++-backed Python interface to the hallmodel kernel.

Compiles the pure-C++ kernel (vendored as a git submodule at
external/hallmodel-core) together with the pybind11 bindings into the
_bw_cpp extension. -ffp-contract=off matches the flag the upstream R
package compiles with, so the arithmetic is byte-for-byte reproducible
against the parity contract.
"""
from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

CORE = "external/hallmodel-core"

ext_modules = [
    Pybind11Extension(
        "_bw_cpp",
        sources=[
            "bindings/bw_cpp.cpp",
            f"{CORE}/src/adult.cpp",
            f"{CORE}/src/child.cpp",
            f"{CORE}/src/energy.cpp",
        ],
        include_dirs=[f"{CORE}/include"],
        cxx_std=17,
        extra_compile_args=["-ffp-contract=off"],
    ),
]

setup(
    name="hallmodel",
    version="0.1.0",
    packages=["bw_cpp"],
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
)
