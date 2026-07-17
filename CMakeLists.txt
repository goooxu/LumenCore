cmake_minimum_required(VERSION 3.20)
project(LumenCore LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CUDA_STANDARD_REQUIRED ON)

# Prefer an explicit -DCMAKE_CUDA_ARCHITECTURES=...; otherwise detect from the first GPU.
# Any NVIDIA GPU with hardware ray tracing (RT Cores) is fine — do not hardcode a SKU/arch.
if(NOT DEFINED CMAKE_CUDA_ARCHITECTURES OR "${CMAKE_CUDA_ARCHITECTURES}" STREQUAL "")
  execute_process(
    COMMAND nvidia-smi --query-gpu=compute_cap --format=csv,noheader
    OUTPUT_VARIABLE _NRTX_CAPS
    RESULT_VARIABLE _NRTX_CAPS_RC
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
  set(_NRTX_ARCH "")
  if(_NRTX_CAPS_RC EQUAL 0 AND NOT "${_NRTX_CAPS}" STREQUAL "")
    string(REGEX REPLACE "\r?\n.*" "" _NRTX_CAP "${_NRTX_CAPS}")
    string(STRIP "${_NRTX_CAP}" _NRTX_CAP)
    string(REPLACE "." "" _NRTX_ARCH "${_NRTX_CAP}")
  endif()
  if(_NRTX_ARCH STREQUAL "")
    message(FATAL_ERROR
      "Could not detect GPU compute capability via nvidia-smi.\n"
      "Set -DCMAKE_CUDA_ARCHITECTURES=<NN> manually "
      "(compute_cap X.Y → XY, e.g. 8.9 → 89).\n"
      "Requires an NVIDIA GPU with hardware ray tracing (RT Cores).")
  endif()
  set(CMAKE_CUDA_ARCHITECTURES "${_NRTX_ARCH}")
  message(STATUS "Detected CMAKE_CUDA_ARCHITECTURES=${CMAKE_CUDA_ARCHITECTURES}")
endif()

find_package(CUDAToolkit REQUIRED)
find_package(Python3 COMPONENTS Interpreter Development.Module REQUIRED)

include(FetchContent)
FetchContent_Declare(
  pybind11
  GIT_REPOSITORY https://github.com/pybind/pybind11.git
  GIT_TAG v2.13.6
)
FetchContent_MakeAvailable(pybind11)

set(OPTIX_INCLUDE_DIR "${CMAKE_SOURCE_DIR}/third_party/optix" CACHE PATH "OptiX include directory")
if(NOT EXISTS "${OPTIX_INCLUDE_DIR}/optix.h")
  message(FATAL_ERROR "OptiX headers not found at ${OPTIX_INCLUDE_DIR}")
endif()

set(PHYSX_ROOT "${CMAKE_SOURCE_DIR}/third_party/physx" CACHE PATH "PhysX 5 install root (include/ + lib/)")
set(PHYSX_LIB_DIR "${PHYSX_ROOT}/lib")
set(PHYSX_INCLUDE_DIR "${PHYSX_ROOT}/include")
if(NOT EXISTS "${PHYSX_LIB_DIR}/libPhysX_static_64.a")
  message(FATAL_ERROR
    "PhysX static libraries not found under ${PHYSX_LIB_DIR}.\n"
    "Run scripts/setup_physx.sh (requires network on first fetch) or set -DPHYSX_ROOT=...")
endif()

find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBHEIF REQUIRED libheif)

add_library(nrtx_host
  src/host/mesh.cpp
  src/host/obj_loader.cpp
  src/host/physx_world.cpp
  src/host/renderer.cpp
  src/host/env_map.cpp
  src/host/heic_writer.cpp
)
target_include_directories(nrtx_host
  PUBLIC
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/src/common
    ${OPTIX_INCLUDE_DIR}
    ${CMAKE_SOURCE_DIR}/third_party
    ${PHYSX_INCLUDE_DIR}
    ${CUDAToolkit_INCLUDE_DIRS}
  PRIVATE
    ${LIBHEIF_INCLUDE_DIRS}
)
target_compile_definitions(nrtx_host PUBLIC PX_PHYSX_STATIC_LIB)
target_link_libraries(nrtx_host PUBLIC
  CUDA::cudart
  CUDA::cuda_driver
  ${PHYSX_LIB_DIR}/libPhysXExtensions_static_64.a
  ${PHYSX_LIB_DIR}/libPhysX_static_64.a
  ${PHYSX_LIB_DIR}/libPhysXPvdSDK_static_64.a
  ${PHYSX_LIB_DIR}/libPhysXCooking_static_64.a
  ${PHYSX_LIB_DIR}/libPhysXCommon_static_64.a
  ${PHYSX_LIB_DIR}/libPhysXFoundation_static_64.a
  pthread
  dl
  ${LIBHEIF_LIBRARIES}
)
target_link_directories(nrtx_host PUBLIC ${LIBHEIF_LIBRARY_DIRS})
set_target_properties(nrtx_host PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_compile_options(nrtx_host PRIVATE $<$<COMPILE_LANGUAGE:CXX>:-Wall -Wextra>)

# Compile device programs to OptiX-IR (first listed arch if several were set).
set(NRTX_SHADER_CU ${CMAKE_SOURCE_DIR}/src/device/shaders.cu)
set(NRTX_SHADER_OPTIXIR ${CMAKE_BINARY_DIR}/shaders.optixir)
list(GET CMAKE_CUDA_ARCHITECTURES 0 NRTX_SHADER_ARCH)
set(NRTX_NVCC_ARCH "compute_${NRTX_SHADER_ARCH}")
message(STATUS "OptiX-IR nvcc -arch=${NRTX_NVCC_ARCH}")

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
