# Fetch OptiX SDK headers from NVIDIA/optix-dev (runtime is the GPU driver).
# Override with -DOPTIX_INCLUDE_DIR=/path if headers are preinstalled.

if(OPTIX_INCLUDE_DIR AND EXISTS "${OPTIX_INCLUDE_DIR}/optix.h")
  message(STATUS "Using pre-set OPTIX_INCLUDE_DIR=${OPTIX_INCLUDE_DIR}")
else()
  set(_LUMENCORE_OPTIX_TAG "v9.1.0" CACHE STRING "NVIDIA/optix-dev git tag")

  if(LUMENCORE_FETCH_DEPS)
    include(FetchContent)
    FetchContent_Declare(
      optix_dev
      GIT_REPOSITORY https://github.com/NVIDIA/optix-dev.git
      GIT_TAG ${_LUMENCORE_OPTIX_TAG}
      GIT_SHALLOW TRUE
    )
    FetchContent_GetProperties(optix_dev)
    if(NOT optix_dev_POPULATED)
      message(STATUS "Fetching OptiX headers (${_LUMENCORE_OPTIX_TAG})...")
      FetchContent_Populate(optix_dev)
    endif()
    if(EXISTS "${optix_dev_SOURCE_DIR}/include/optix.h")
      set(OPTIX_INCLUDE_DIR "${optix_dev_SOURCE_DIR}/include" CACHE PATH "OptiX include directory" FORCE)
    elseif(EXISTS "${optix_dev_SOURCE_DIR}/optix.h")
      set(OPTIX_INCLUDE_DIR "${optix_dev_SOURCE_DIR}" CACHE PATH "OptiX include directory" FORCE)
    else()
      message(FATAL_ERROR
        "Fetched optix-dev but optix.h not found under ${optix_dev_SOURCE_DIR}")
    endif()
  elseif(EXISTS "${CMAKE_SOURCE_DIR}/third_party/optix/optix.h")
    set(OPTIX_INCLUDE_DIR "${CMAKE_SOURCE_DIR}/third_party/optix" CACHE PATH "OptiX include directory")
  endif()
endif()

if(NOT EXISTS "${OPTIX_INCLUDE_DIR}/optix.h")
  message(FATAL_ERROR
    "OptiX headers not found (looked for optix.h).\n"
    "Enable LUMENCORE_FETCH_DEPS=ON (network) or pass -DOPTIX_INCLUDE_DIR=...")
endif()
message(STATUS "OptiX headers: ${OPTIX_INCLUDE_DIR}")
