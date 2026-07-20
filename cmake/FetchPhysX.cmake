# Build or locate PhysX 5 static libs.
# Override with -DPHYSX_ROOT=/path (include/ + lib/ + bin/).

set(_LUMENCORE_PHYSX_TAG "106.1-physx-5.4.2" CACHE STRING "PhysX git tag")
set(_LUMENCORE_PHYSX_INSTALL "${CMAKE_BINARY_DIR}/_deps/physx")

if(PHYSX_ROOT AND EXISTS "${PHYSX_ROOT}/lib/libPhysX_static_64.a")
  message(STATUS "Using pre-set PHYSX_ROOT=${PHYSX_ROOT}")
elseif(LUMENCORE_FETCH_DEPS)
  set(PHYSX_ROOT "${_LUMENCORE_PHYSX_INSTALL}" CACHE PATH "PhysX 5 install root" FORCE)
  set(_physx_src "${CMAKE_BINARY_DIR}/_deps/physx-src")
  set(_physx_script "${CMAKE_SOURCE_DIR}/scripts/fetch_physx.sh")
  if(NOT EXISTS "${_physx_script}")
    message(FATAL_ERROR "Missing ${_physx_script}")
  endif()

  if(NOT EXISTS "${PHYSX_ROOT}/lib/libPhysX_static_64.a")
    message(STATUS
      "Building PhysX ${_LUMENCORE_PHYSX_TAG} into ${PHYSX_ROOT} "
      "(first configure may take several minutes)...")
    set(_physx_jobs "")
    if(DEFINED ENV{CMAKE_BUILD_PARALLEL_LEVEL} AND NOT "$ENV{CMAKE_BUILD_PARALLEL_LEVEL}" STREQUAL "")
      set(_physx_jobs "$ENV{CMAKE_BUILD_PARALLEL_LEVEL}")
    else()
      include(ProcessorCount)
      ProcessorCount(_nproc)
      if(_nproc AND NOT _nproc EQUAL 0)
        set(_physx_jobs "${_nproc}")
      else()
        set(_physx_jobs "4")
      endif()
    endif()

    # Prefer CMake's C/CXX compilers when set; fall back to gcc/g++ inside the script.
    set(_physx_cc "${CMAKE_C_COMPILER}")
    set(_physx_cxx "${CMAKE_CXX_COMPILER}")
    if(NOT _physx_cc)
      set(_physx_cc "gcc")
    endif()
    if(NOT _physx_cxx)
      set(_physx_cxx "g++")
    endif()

    execute_process(
      COMMAND ${CMAKE_COMMAND} -E env
        "PHYSX_SRC=${_physx_src}"
        "PHYSX_INSTALL=${PHYSX_ROOT}"
        "PHYSX_TAG=${_LUMENCORE_PHYSX_TAG}"
        "PHYSX_JOBS=${_physx_jobs}"
        "CC=${_physx_cc}"
        "CXX=${_physx_cxx}"
        "PATH=$ENV{PATH}"
        bash "${_physx_script}"
      WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
      RESULT_VARIABLE _physx_rc
      OUTPUT_VARIABLE _physx_out
      ERROR_VARIABLE _physx_err
    )
    if(NOT _physx_rc EQUAL 0)
      message(FATAL_ERROR
        "PhysX fetch/build failed (exit ${_physx_rc}).\n"
        "--- stdout ---\n${_physx_out}\n"
        "--- stderr ---\n${_physx_err}\n"
        "Preinstall and pass -DPHYSX_ROOT=... or re-run with network access.")
    endif()
    message(STATUS "PhysX install complete: ${PHYSX_ROOT}")
  else()
    message(STATUS "PhysX already built at ${PHYSX_ROOT}")
  endif()
elseif(EXISTS "${CMAKE_SOURCE_DIR}/third_party/physx/lib/libPhysX_static_64.a")
  set(PHYSX_ROOT "${CMAKE_SOURCE_DIR}/third_party/physx" CACHE PATH "PhysX 5 install root")
endif()

set(PHYSX_LIB_DIR "${PHYSX_ROOT}/lib")
set(PHYSX_INCLUDE_DIR "${PHYSX_ROOT}/include")
set(PHYSX_BIN_DIR "${PHYSX_ROOT}/bin")

if(NOT EXISTS "${PHYSX_LIB_DIR}/libPhysX_static_64.a")
  message(FATAL_ERROR
    "PhysX static libraries not found under ${PHYSX_LIB_DIR}.\n"
    "Enable LUMENCORE_FETCH_DEPS=ON (network + gcc) or set -DPHYSX_ROOT=...")
endif()
if(NOT EXISTS "${PHYSX_INCLUDE_DIR}/PxPhysicsAPI.h")
  message(FATAL_ERROR "PhysX headers not found under ${PHYSX_INCLUDE_DIR}")
endif()

message(STATUS "PhysX root: ${PHYSX_ROOT}")
if(EXISTS "${PHYSX_BIN_DIR}/libPhysXGpu_64.so")
  message(STATUS "PhysX GPU runtime: ${PHYSX_BIN_DIR}/libPhysXGpu_64.so")
else()
  message(WARNING "libPhysXGpu_64.so not under ${PHYSX_BIN_DIR}; GPU PhysX may fail at runtime")
endif()

if(NOT TARGET lumencore_physx)
  add_library(lumencore_physx INTERFACE)
  target_include_directories(lumencore_physx INTERFACE "${PHYSX_INCLUDE_DIR}")
  target_compile_definitions(lumencore_physx INTERFACE PX_PHYSX_STATIC_LIB)
  target_link_libraries(lumencore_physx INTERFACE
    "${PHYSX_LIB_DIR}/libPhysXExtensions_static_64.a"
    "${PHYSX_LIB_DIR}/libPhysX_static_64.a"
    "${PHYSX_LIB_DIR}/libPhysXPvdSDK_static_64.a"
    "${PHYSX_LIB_DIR}/libPhysXCooking_static_64.a"
    "${PHYSX_LIB_DIR}/libPhysXCommon_static_64.a"
    "${PHYSX_LIB_DIR}/libPhysXFoundation_static_64.a"
    pthread
    dl
  )
endif()
