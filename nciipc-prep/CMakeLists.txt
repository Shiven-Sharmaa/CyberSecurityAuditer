cmake_minimum_required(VERSION 3.16)
project(nciipc_prep)
set(CMAKE_CXX_STANDARD 17)

# Auto-detect pybind11's CMake config from the active Python environment
# (activate your venv before running cmake so this picks up the right pybind11)
find_package(Python3 COMPONENTS Interpreter Development.Module REQUIRED)
execute_process(
  COMMAND "${Python3_EXECUTABLE}" -m pybind11 --cmakedir
  OUTPUT_VARIABLE pybind11_DIR
  OUTPUT_STRIP_TRAILING_WHITESPACE
)
find_package(pybind11 REQUIRED)

set(SOURCES src/chunker.cpp src/bm25.cpp)
pybind11_add_module(nciipc_cpp src/bindings.cpp ${SOURCES})
target_include_directories(nciipc_cpp PRIVATE include)

if(MSVC)
  target_compile_options(nciipc_cpp PRIVATE /O2)
else()
  target_compile_options(nciipc_cpp PRIVATE -O3 -march=native)
endif()