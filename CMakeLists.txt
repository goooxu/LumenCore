cmake_minimum_required(VERSION 3.20)
project(LumenCore LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CUDA_STANDARD_REQUIRED ON)

if(NOT DEFINED CMAKE_CUDA_ARCHITECTURES)
  set(CMAKE_CUDA_ARCHITECTURES 120)
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

add_library(nrtx_host
  src/host/mesh.cpp
  src/host/obj_loader.cpp
  src/host/renderer.cpp
)
target_include_directories(nrtx_host
  PUBLIC
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/src/common
    ${OPTIX_INCLUDE_DIR}
    ${CMAKE_SOURCE_DIR}/third_party
    ${CUDAToolkit_INCLUDE_DIRS}
)
target_link_libraries(nrtx_host PUBLIC CUDA::cudart CUDA::cuda_driver)
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

option(LUMENCORE_BUILD_CPP_EXAMPLES "Build legacy C++ example binaries" OFF)
if(LUMENCORE_BUILD_CPP_EXAMPLES)
  function(nrtx_add_example name)
    add_executable(${name} examples/${name}.cc)
    target_link_libraries(${name} PRIVATE nrtx_host)
    add_dependencies(${name} nrtx_shaders)
    set_target_properties(${name} PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
  endfunction()
  nrtx_add_example(cornell)
  nrtx_add_example(materials_ball)
  nrtx_add_example(outdoor_env)
  nrtx_add_example(yellow_buddy)
endif()
