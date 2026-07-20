cmake_minimum_required(VERSION 3.20)

# CUDA arch must be set before project(LANGUAGES CUDA), otherwise CMake injects a default.
if(NOT DEFINED CMAKE_CUDA_ARCHITECTURES OR CMAKE_CUDA_ARCHITECTURES STREQUAL "")
  execute_process(
    COMMAND nvidia-smi --query-gpu=compute_cap --format=csv,noheader
    OUTPUT_VARIABLE _NRTX_COMPUTE_CAP
    RESULT_VARIABLE _NRTX_SMI_RC
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
  if(NOT _NRTX_SMI_RC EQUAL 0 OR _NRTX_COMPUTE_CAP STREQUAL "")
    message(FATAL_ERROR
      "CMAKE_CUDA_ARCHITECTURES not set and nvidia-smi compute_cap detection failed.\n"
      "Pass -DCMAKE_CUDA_ARCHITECTURES=<NN> (e.g. 89, 90, 100, 120) for your GPU.")
  endif()
  string(REGEX REPLACE "\n.*" "" _NRTX_COMPUTE_CAP "${_NRTX_COMPUTE_CAP}")
  string(STRIP "${_NRTX_COMPUTE_CAP}" _NRTX_COMPUTE_CAP)
  string(REGEX REPLACE "^([0-9]+)\\.([0-9]+)$" "\\1\\2" _NRTX_CUDA_ARCH
                       "${_NRTX_COMPUTE_CAP}")
  if(_NRTX_CUDA_ARCH STREQUAL "${_NRTX_COMPUTE_CAP}")
    message(FATAL_ERROR
      "Could not parse compute_cap '${_NRTX_COMPUTE_CAP}'. "
      "Pass -DCMAKE_CUDA_ARCHITECTURES=<NN> explicitly.")
  endif()
  set(CMAKE_CUDA_ARCHITECTURES "${_NRTX_CUDA_ARCH}" CACHE STRING
      "CUDA architectures (auto-detected from nvidia-smi unless overridden)" FORCE)
  message(STATUS "Detected CMAKE_CUDA_ARCHITECTURES=${CMAKE_CUDA_ARCHITECTURES} "
                 "(from nvidia-smi compute_cap=${_NRTX_COMPUTE_CAP})")
endif()

project(LumenCore LANGUAGES C CXX CUDA)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CUDA_STANDARD_REQUIRED ON)

find_package(CUDAToolkit REQUIRED)
find_package(Python3 COMPONENTS Interpreter Development.Module REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(AVIF REQUIRED IMPORTED_TARGET libavif)

# Third-party: OptiX headers, PhysX, stb, pybind11 (fetched when LUMENCORE_FETCH_DEPS=ON).
include(${CMAKE_SOURCE_DIR}/cmake/Dependencies.cmake)

add_library(nrtx_host
  src/host/mesh.cpp
  src/host/obj_loader.cpp
  src/host/physx_world.cpp
  src/host/renderer.cpp
  src/host/env_map.cpp
  src/host/image_io.cpp
)
target_include_directories(nrtx_host
  PUBLIC
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/src/common
    ${OPTIX_INCLUDE_DIR}
    ${STB_INCLUDE_DIR}
    ${CUDAToolkit_INCLUDE_DIRS}
)
target_link_libraries(nrtx_host PUBLIC
  CUDA::cudart
  CUDA::cuda_driver
  PkgConfig::AVIF
  lumencore_physx
)
set_target_properties(nrtx_host PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_compile_options(nrtx_host PRIVATE $<$<COMPILE_LANGUAGE:CXX>:-Wall -Wextra>)

# Compile device programs to OptiX-IR
set(NRTX_SHADER_CU ${CMAKE_SOURCE_DIR}/src/device/shaders.cu)
set(NRTX_SHADER_OPTIXIR ${CMAKE_BINARY_DIR}/shaders.optixir)
set(NRTX_NVCC_ARCH "compute_${CMAKE_CUDA_ARCHITECTURES}")

add_custom_command(
  OUTPUT ${NRTX_SHADER_OPTIXIR}
  COMMAND ${CMAKE_CUDA_COMPILER}
    -optix-ir
    -I${CMAKE_SOURCE_DIR}/src/common
    -I${OPTIX_INCLUDE_DIR}
    -I${CUDAToolkit_INCLUDE_DIRS}
    --std=c++17
    -O3
    -arch=${NRTX_NVCC_ARCH}
    ${NRTX_SHADER_CU}
    -o ${NRTX_SHADER_OPTIXIR}
  DEPENDS ${NRTX_SHADER_CU}
    ${CMAKE_SOURCE_DIR}/src/common/LaunchParams.h
    ${CMAKE_SOURCE_DIR}/src/common/vec.h
    ${CMAKE_SOURCE_DIR}/src/common/sampling.h
    ${CMAKE_SOURCE_DIR}/src/common/bsdf.h
  COMMENT "Compiling OptiX device programs to OptiX-IR"
  VERBATIM
)

add_custom_target(nrtx_shaders ALL DEPENDS ${NRTX_SHADER_OPTIXIR})

pybind11_add_module(lumencore bindings/lumencore_module.cpp)
target_link_libraries(lumencore PRIVATE nrtx_host)
add_dependencies(lumencore nrtx_shaders)
set_target_properties(lumencore PROPERTIES
  LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/python
  RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/python
)

# Export PhysX GPU lib dir for run scripts (written next to the build tree).
file(WRITE "${CMAKE_BINARY_DIR}/lumencore_env.sh"
"export PHYSX_ROOT=\"${PHYSX_ROOT}\"
export LD_LIBRARY_PATH=\"${PHYSX_BIN_DIR}\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}\"
export NRTX_PTX=\"${NRTX_SHADER_OPTIXIR}\"
export PYTHONPATH=\"${CMAKE_BINARY_DIR}/python\${PYTHONPATH:+:\$PYTHONPATH}\"
export LUMENCORE_ROOT=\"${CMAKE_SOURCE_DIR}\"
")
